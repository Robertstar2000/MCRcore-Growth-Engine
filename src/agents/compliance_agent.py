"""
MCRcore Growth Engine - Compliance & Deliverability Agent

Gates ALL outbound email communications.  No email leaves the system
without passing every check in this agent's ``run_full_check()`` method.

Checks enforced (all must pass):
  1. Suppression check   - email not on suppression list
  2. Opt-out check       - lead has not opted out
  3. Source approval      - lead source is approved for outreach
  4. Contact validity     - valid email format, not bounced
  5. Sender identity      - From address is an approved sender
  6. Subject line         - not empty, not deceptive, under 150 chars
  7. Footer               - contains physical address (CAN-SPAM)
  8. Unsubscribe          - contains unsubscribe mechanism text
  9. Domain auth          - SPF/DKIM/DMARC placeholder validation

Results are returned as a ComplianceResult dataclass and every check
is audit-logged.  Failures trigger a Teams alert.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.base_agent import BaseAgent
from src.skills.compliance_check import (
    APPROVED_SENDER_ADDRESSES,
    APPROVED_SENDER_DOMAINS,
    CAN_SPAM_CHECKLIST,
    DOMAIN_AUTH_CONFIGS,
    PHYSICAL_ADDRESS,
    ROLE_ADDRESS_PREFIXES,
    body_has_physical_address,
    body_has_unsubscribe,
    validate_subject_line,
)
from src.services.suppression_manager import SuppressionManager
from src.services.deliverability_monitor import DeliverabilityMonitor
from src.utils.email_validator import validate_email_format, estimate_bounce_risk
from src.utils.teams_notifier import send_teams_card, send_teams_message


# -----------------------------------------------------------------------
# Result dataclass
# -----------------------------------------------------------------------

@dataclass
class ComplianceResult:
    """Outcome of a full compliance check run."""

    approved: bool = False
    checks_passed: List[str] = field(default_factory=list)
    checks_failed: List[str] = field(default_factory=list)
    corrective_notes: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "corrective_notes": self.corrective_notes,
            "risk_flags": self.risk_flags,
        }


# -----------------------------------------------------------------------
# Draft email structure
# -----------------------------------------------------------------------

@dataclass
class DraftEmail:
    """Lightweight container for a draft outbound email."""

    to_email: str = ""
    from_addr: str = ""
    subject: str = ""
    body: str = ""
    sending_domain: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "DraftEmail":
        return cls(
            to_email=d.get("to_email", d.get("to", "")),
            from_addr=d.get("from_addr", d.get("from", "")),
            subject=d.get("subject", ""),
            body=d.get("body", ""),
            sending_domain=d.get("sending_domain", ""),
        )


# -----------------------------------------------------------------------
# Compliance Agent
# -----------------------------------------------------------------------

class ComplianceAgent(BaseAgent):
    """
    Deliverability and CAN-SPAM compliance gatekeeper.

    Every outbound email must be approved by ``run_full_check()`` before
    it is transmitted.
    """

    def __init__(
        self,
        db_session=None,
        suppression_manager: SuppressionManager = None,
        deliverability_monitor: DeliverabilityMonitor = None,
    ):
        super().__init__(
            name="ComplianceAgent",
            description="Gates all outbound communications for CAN-SPAM and deliverability compliance.",
        )
        self._session = db_session
        self._suppression = suppression_manager or SuppressionManager(db_session)
        self._deliverability = deliverability_monitor or DeliverabilityMonitor(db_session)

        # DB repositories (lazily loaded)
        self._lead_repo = None
        self._source_repo = None
        self._audit_repo = None
        if db_session is not None:
            try:
                from db.repositories import LeadRepository, SourceRepository, AuditRepository
                self._lead_repo = LeadRepository(db_session)
                self._source_repo = SourceRepository(db_session)
                self._audit_repo = AuditRepository(db_session)
            except Exception as exc:
                self.logger.warning(f"Could not initialise DB repos: {exc}")

    # ==================================================================
    # run() - BaseAgent interface
    # ==================================================================

    def run(self, lead_id: str = None, draft_email: dict = None, **kwargs) -> Dict[str, Any]:
        """
        Execute the agent's primary task: run a full compliance check.

        Args:
            lead_id:     Lead identifier.
            draft_email: Dict with keys to_email, from_addr, subject, body,
                         sending_domain.

        Returns:
            ComplianceResult as dict.
        """
        if draft_email is None:
            draft_email = kwargs
        result = self.run_full_check(lead_id, draft_email)
        return result.to_dict()

    # ==================================================================
    # Main entry point
    # ==================================================================

    def check_send_approval(self, lead_id: str, draft_email: dict) -> ComplianceResult:
        """Alias for run_full_check kept for backwards compatibility."""
        return self.run_full_check(lead_id, draft_email)

    def run_full_check(self, lead_id: str, draft_email: dict) -> ComplianceResult:
        """
        Run ALL 9 compliance checks in sequence.

        Every check is run even if earlier checks fail (so that the
        caller receives the complete picture).

        Args:
            lead_id:     The lead's primary-key identifier.
            draft_email: Dict with to_email, from_addr, subject, body,
                         sending_domain.

        Returns:
            ComplianceResult with pass/fail and detailed notes.
        """
        draft = DraftEmail.from_dict(draft_email) if isinstance(draft_email, dict) else draft_email
        result = ComplianceResult()

        # Derive sending domain from from_addr if not explicitly set
        if not draft.sending_domain and draft.from_addr and "@" in draft.from_addr:
            draft.sending_domain = draft.from_addr.split("@")[-1].lower()

        # --- 1. Suppression check ----
        ok, notes = self.validate_suppression(draft.to_email)
        self._record_check(result, "suppression_check", ok, notes)

        # --- 2. Opt-out check ----
        ok, notes = self.validate_opt_out(lead_id)
        self._record_check(result, "opt_out_check", ok, notes)

        # --- 3. Source approval check ----
        ok, notes = self.validate_source_approval(lead_id)
        self._record_check(result, "source_approval_check", ok, notes)

        # --- 4. Contact validity check ----
        ok, notes = self.validate_contact(draft.to_email)
        self._record_check(result, "contact_validity_check", ok, notes)

        # --- 5. Sender identity check ----
        ok, notes = self.validate_sender_identity(draft.from_addr)
        self._record_check(result, "sender_identity_check", ok, notes)

        # --- 6. Subject line check ----
        ok, notes = self.validate_subject_line(draft.subject)
        self._record_check(result, "subject_line_check", ok, notes)

        # --- 7. Footer check ----
        ok, notes = self.validate_footer(draft.body)
        self._record_check(result, "footer_check", ok, notes)

        # --- 8. Unsubscribe check ----
        ok, notes = self.validate_unsubscribe(draft.body)
        self._record_check(result, "unsubscribe_check", ok, notes)

        # --- 9. Domain auth check ----
        ok, notes = self.validate_domain_auth(draft.sending_domain)
        self._record_check(result, "domain_auth_check", ok, notes)

        # --- Final verdict ----
        result.approved = len(result.checks_failed) == 0

        # Audit the full result
        self.log_action(
            action="compliance_full_check",
            detail=(
                f"lead={lead_id} to={draft.to_email} "
                f"approved={result.approved} "
                f"passed={len(result.checks_passed)}/9 "
                f"failed={len(result.checks_failed)}"
            ),
            status="success" if result.approved else "failure",
            metadata=result.to_dict(),
        )

        # DB audit
        if self._audit_repo is not None:
            try:
                self._audit_repo.log(
                    actor="ComplianceAgent",
                    entity_type="compliance_check",
                    entity_id=lead_id or "unknown",
                    action="full_check",
                    after_json=json.dumps(result.to_dict()),
                )
                if self._session:
                    self._session.commit()
            except Exception as exc:
                self.logger.error(f"Audit DB write failed: {exc}")

        # Teams alert on failure
        if not result.approved:
            self._send_failure_alert(lead_id, draft, result)

        return result

    # ==================================================================
    # Individual checks
    # ==================================================================

    def validate_suppression(self, email: str) -> tuple:
        """Check that the email is NOT on the suppression list."""
        if not email:
            return False, ["No recipient email provided."]

        if self._suppression.is_suppressed(email):
            return False, [f"Email {email} is on the suppression list."]

        # Also check for role-based addresses
        email_lower = email.strip().lower()
        for prefix in ROLE_ADDRESS_PREFIXES:
            if email_lower.startswith(prefix):
                return False, [
                    f"Email {email} is a role-based address ({prefix}*) "
                    "which is excluded by policy."
                ]

        return True, ["Suppression check passed."]

    def validate_opt_out(self, lead_id: str) -> tuple:
        """Check that the lead has not opted out."""
        if not lead_id:
            return False, ["No lead_id provided for opt-out check."]

        if self._lead_repo is not None:
            try:
                lead = self._lead_repo.get_by_id(lead_id)
                if lead is None:
                    return False, [f"Lead {lead_id} not found in database."]
                if lead.opt_out_flag:
                    return False, [f"Lead {lead_id} has opted out."]
                if lead.do_not_contact_reason:
                    return False, [
                        f"Lead {lead_id} marked do-not-contact: "
                        f"{lead.do_not_contact_reason}"
                    ]
                return True, ["Opt-out check passed."]
            except Exception as exc:
                self.logger.error(f"Opt-out DB check failed: {exc}")
                return False, [f"Opt-out check failed (DB error): {exc}"]

        # No DB - pass with risk flag
        return True, ["Opt-out check passed (no DB - manual verification advised)."]

    def validate_source_approval(self, lead_id: str) -> tuple:
        """Check that the lead's source is approved for outreach."""
        if not lead_id:
            return False, ["No lead_id provided for source approval check."]

        if self._lead_repo is not None and self._source_repo is not None:
            try:
                lead = self._lead_repo.get_by_id(lead_id)
                if lead is None:
                    return False, [f"Lead {lead_id} not found."]
                if not lead.source_id:
                    return False, [f"Lead {lead_id} has no source_id assigned."]

                source = self._source_repo.get_by_id(lead.source_id)
                if source is None:
                    return False, [f"Source {lead.source_id} not found."]
                if not source.approved_flag:
                    return False, [
                        f"Source '{source.source_name}' (id={source.source_id}) "
                        "is not approved for outreach."
                    ]
                if source.risk_level == "high":
                    return True, [
                        f"Source '{source.source_name}' is approved but "
                        "risk_level=high. Proceed with caution."
                    ]
                return True, [
                    f"Source '{source.source_name}' is approved "
                    f"(risk={source.risk_level})."
                ]
            except Exception as exc:
                self.logger.error(f"Source approval DB check failed: {exc}")
                return False, [f"Source approval check failed (DB error): {exc}"]

        # No DB
        return True, ["Source approval check passed (no DB - manual verification advised)."]

    def validate_contact(self, email: str) -> tuple:
        """Validate email format and bounce risk."""
        if not email:
            return False, ["No recipient email provided."]

        # Format validation
        if not validate_email_format(email):
            return False, [f"Email '{email}' has an invalid format."]

        # Bounce risk estimation
        risk_level, risk_score = estimate_bounce_risk(email)
        if risk_level == "high":
            return False, [
                f"Email '{email}' has HIGH bounce risk (score={risk_score:.2f}). "
                "Do not send."
            ]

        notes = [f"Contact validity passed (risk={risk_level}, score={risk_score:.2f})."]
        return True, notes

    def validate_sender_identity(self, from_addr: str) -> tuple:
        """Verify the From address is an approved sender."""
        if not from_addr:
            return False, ["No From address provided."]

        from_addr_lower = from_addr.strip().lower()

        # Check exact address match
        if from_addr_lower in [a.lower() for a in APPROVED_SENDER_ADDRESSES]:
            return True, [f"Sender '{from_addr}' is an approved address."]

        # Check domain match
        if "@" in from_addr_lower:
            domain = from_addr_lower.split("@")[-1]
            if domain in [d.lower() for d in APPROVED_SENDER_DOMAINS]:
                return True, [
                    f"Sender '{from_addr}' is from approved domain '{domain}'."
                ]

        return False, [
            f"Sender '{from_addr}' is NOT an approved sender. "
            f"Approved addresses: {', '.join(APPROVED_SENDER_ADDRESSES)}. "
            f"Approved domains: {', '.join(APPROVED_SENDER_DOMAINS)}."
        ]

    def validate_subject_line(self, subject: str) -> tuple:
        """Validate subject line for CAN-SPAM and deliverability."""
        passed, issues = validate_subject_line(subject)
        if passed:
            return True, ["Subject line check passed."]
        return False, issues

    def validate_footer(self, body: str) -> tuple:
        """Verify the email body contains the required physical address."""
        found, detail = body_has_physical_address(body)
        if found:
            return True, [detail]
        return False, [
            detail,
            f"CAN-SPAM requires a physical postal address. "
            f"Add: {PHYSICAL_ADDRESS}",
        ]

    def validate_unsubscribe(self, body: str) -> tuple:
        """Verify the email body contains an unsubscribe mechanism."""
        found, detail = body_has_unsubscribe(body)
        if found:
            return True, [detail]
        return False, [
            detail,
            "CAN-SPAM requires a clear unsubscribe mechanism. "
            "Add unsubscribe text or link to the email body.",
        ]

    def validate_domain_auth(self, domain: str) -> tuple:
        """
        Placeholder check for SPF / DKIM / DMARC configuration.

        In production this would query DNS TXT records.  For now we
        validate against the known domain auth configs.
        """
        if not domain:
            return False, ["No sending domain provided for auth check."]

        domain_lower = domain.strip().lower()
        config = DOMAIN_AUTH_CONFIGS.get(domain_lower)

        if config is None:
            return False, [
                f"Domain '{domain}' has no auth config registered. "
                "SPF/DKIM/DMARC status unknown. Add config before sending."
            ]

        # Placeholder: assume configured domains are properly set up
        notes = []
        passed = True

        if config.spf_expected:
            notes.append(f"SPF: expected=True (placeholder pass for {domain})")
        if config.dkim_expected:
            notes.append(f"DKIM: expected=True (placeholder pass for {domain})")
        if config.dmarc_expected:
            notes.append(
                f"DMARC: expected=True policy={config.dmarc_policy} "
                f"(placeholder pass for {domain})"
            )

        return passed, notes

    # ==================================================================
    # Deliverability gate (wraps deliverability_monitor)
    # ==================================================================

    def is_sending_safe(self, domain: str = None) -> tuple:
        """
        Check whether the system is safe to send right now.

        Combines kill-switch check and domain throttle check.
        """
        if self._deliverability.should_pause_sending():
            return False, "Sending is paused by kill-switch."

        if domain:
            allowed, reason = self._deliverability.can_send_for_domain(domain)
            if not allowed:
                return False, reason

        return True, "System is safe to send."

    # ==================================================================
    # Helpers
    # ==================================================================

    def _record_check(
        self,
        result: ComplianceResult,
        check_name: str,
        passed: bool,
        notes: List[str],
    ):
        """Record a single check's outcome into the ComplianceResult."""
        if passed:
            result.checks_passed.append(check_name)
        else:
            result.checks_failed.append(check_name)
            result.corrective_notes.extend(notes)

        # Flag risk items even on pass
        for note in notes:
            lower = note.lower()
            if any(w in lower for w in ["risk", "caution", "manual verification"]):
                result.risk_flags.append(f"[{check_name}] {note}")

        # Audit each individual check
        self.log_action(
            action=f"check_{check_name}",
            detail=f"{'PASS' if passed else 'FAIL'}: {'; '.join(notes)}",
            status="success" if passed else "failure",
            metadata={"check": check_name, "passed": passed, "notes": notes},
        )

    def _send_failure_alert(
        self,
        lead_id: str,
        draft: DraftEmail,
        result: ComplianceResult,
    ):
        """Send a Teams alert when a compliance check fails."""
        facts = [
            {"title": "Lead ID", "value": str(lead_id or "N/A")},
            {"title": "To", "value": draft.to_email or "N/A"},
            {"title": "From", "value": draft.from_addr or "N/A"},
            {"title": "Subject", "value": (draft.subject or "N/A")[:80]},
            {"title": "Checks Failed", "value": ", ".join(result.checks_failed)},
            {"title": "Checks Passed", "value": ", ".join(result.checks_passed)},
        ]

        send_teams_card(
            title="⛔ Compliance Check FAILED - Email Blocked",
            facts=facts,
        )
