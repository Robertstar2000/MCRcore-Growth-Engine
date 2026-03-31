"""
MCRcore Growth Engine - Source Compliance Agent

Validates every lead source against the allowlist defined in
config/source_policy.py.  Blocks scraped or disallowed sources,
tags risk levels, and requests human approval via Teams when a
source's status is uncertain or pending review.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from config.source_policy import (
    APPROVED_SOURCES,
    DENYLIST_RULES,
    PENDING_REVIEW_POLICY,
    RISK_SCORING,
    RiskLevel,
    SourceStatus,
)
from db.repositories import AuditRepository, SourceRepository
from src.agents.base_agent import BaseAgent
from src.utils.teams_notifier import send_approval_request, send_teams_card


class SourceComplianceAgent(BaseAgent):
    """
    Validates lead sources against the source policy allowlist,
    blocks disallowed sources, tags risk levels, and manages the
    human-approval workflow for uncertain sources.
    """

    def __init__(self, session: Session):
        super().__init__(
            name="SourceComplianceAgent",
            description=(
                "Validates lead sources against the MCRcore source policy. "
                "Blocks scraped/disallowed sources, tags risk, and manages "
                "human-approval flow via Teams."
            ),
        )
        self.session = session
        self.source_repo = SourceRepository(session)
        self.audit_repo = AuditRepository(session)

        # In-memory pending-approval tracker  {source_name: details_dict}
        self._pending_approvals: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # run() - abstract method implementation
    # ------------------------------------------------------------------
    def run(self, source_name: str, source_type: str = "") -> Dict[str, Any]:
        """
        Main entry point: validate a source and return a compliance result.
        """
        return self.validate_source(source_name, source_type)

    # ------------------------------------------------------------------
    # validate_source
    # ------------------------------------------------------------------
    def validate_source(
        self, source_name: str, source_type: str = ""
    ) -> Dict[str, Any]:
        """
        Validate a lead source against the allowlist and denylist.

        Returns a dict:
            {
                "approved": bool,
                "risk_level": str,
                "reason": str,
                "source_record": Source | None,
                "requires_review": bool,
            }
        """
        self.log_action(
            "validate_source",
            f"Validating source '{source_name}' (type={source_type})",
            status="pending",
        )

        # 1. Check denylist source types
        denied_types = {
            r["type"] for r in DENYLIST_RULES.get("source_types_denied", [])
        }
        if source_type in denied_types:
            reason = self._get_deny_reason(source_type)
            self.log_action(
                "source_blocked",
                f"Source type '{source_type}' is on the denylist: {reason}",
                status="failure",
                metadata={"source_name": source_name, "source_type": source_type},
            )
            return {
                "approved": False,
                "risk_level": RiskLevel.BLOCKED.value,
                "reason": reason,
                "source_record": None,
                "requires_review": False,
            }

        # 2. Check approved sources list
        policy_entry = APPROVED_SOURCES.get(source_name)

        if policy_entry and policy_entry.status == SourceStatus.APPROVED:
            # Ensure DB record exists and is up-to-date
            source_record = self._ensure_source_record(
                source_name,
                source_type or policy_entry.category,
                risk_level=policy_entry.risk_level.value,
                approved=True,
            )
            risk = self.assess_risk(source_record)
            self.log_action(
                "source_approved",
                f"Source '{source_name}' is on the approved list (risk={risk})",
                status="success",
                metadata={
                    "source_name": source_name,
                    "risk_level": risk,
                },
            )
            return {
                "approved": True,
                "risk_level": risk,
                "reason": "Source is on the approved allowlist",
                "source_record": source_record,
                "requires_review": False,
            }

        if policy_entry and policy_entry.status == SourceStatus.DENIED:
            source_record = self._ensure_source_record(
                source_name,
                source_type or policy_entry.category,
                risk_level=RiskLevel.BLOCKED.value,
                approved=False,
            )
            self.log_action(
                "source_denied",
                f"Source '{source_name}' is explicitly denied in policy",
                status="failure",
                metadata={"source_name": source_name},
            )
            return {
                "approved": False,
                "risk_level": RiskLevel.BLOCKED.value,
                "reason": "Source is explicitly denied in source policy",
                "source_record": source_record,
                "requires_review": False,
            }

        # 3. Source not in allowlist → check DB for prior approval
        existing = self.source_repo.find_by_name(source_name)
        if existing and existing.approved_flag:
            risk = self.assess_risk(existing)
            self.log_action(
                "source_approved_db",
                f"Source '{source_name}' previously approved in DB (risk={risk})",
                status="success",
                metadata={"source_name": source_name, "risk_level": risk},
            )
            return {
                "approved": True,
                "risk_level": risk,
                "reason": "Source previously approved (database record)",
                "source_record": existing,
                "requires_review": False,
            }

        # 4. Unknown source → request human review
        source_record = self._ensure_source_record(
            source_name,
            source_type or "unknown",
            risk_level=RiskLevel.HIGH.value,
            approved=False,
        )
        self.request_approval(source_name, {
            "source_type": source_type or "unknown",
            "reason": "Source not found in approved allowlist",
            "review_sla_hours": PENDING_REVIEW_POLICY.get("review_sla_hours", 24),
        })
        self.log_action(
            "source_pending_review",
            f"Source '{source_name}' not in allowlist — human review requested",
            status="pending",
            metadata={"source_name": source_name},
        )
        return {
            "approved": False,
            "risk_level": RiskLevel.HIGH.value,
            "reason": "Source not in allowlist — pending human review",
            "source_record": source_record,
            "requires_review": True,
        }

    # ------------------------------------------------------------------
    # assess_risk
    # ------------------------------------------------------------------
    def assess_risk(self, source_record) -> str:
        """
        Assess the risk level for a source record.

        Uses the source policy entry if available, otherwise falls
        back to the database record's current risk_level.

        Returns the risk level string (low/medium/high/blocked).
        """
        if source_record is None:
            return RiskLevel.HIGH.value

        source_name = source_record.source_name
        policy_entry = APPROVED_SOURCES.get(source_name)

        if policy_entry:
            risk = policy_entry.risk_level.value
        else:
            risk = source_record.risk_level or RiskLevel.HIGH.value

        # Update DB if different
        if source_record.risk_level != risk:
            self.source_repo.update(
                source_record.source_id, risk_level=risk
            )
            self.audit_repo.log(
                actor=self.name,
                entity_type="Source",
                entity_id=source_record.source_id,
                action="update",
                before_json=f'{{"risk_level": "{source_record.risk_level}"}}',
                after_json=f'{{"risk_level": "{risk}"}}',
            )

        self.log_action(
            "assess_risk",
            f"Risk for '{source_name}': {risk}",
            metadata={"source_name": source_name, "risk_level": risk},
        )
        return risk

    # ------------------------------------------------------------------
    # request_approval
    # ------------------------------------------------------------------
    def request_approval(
        self, source_name: str, details: Dict[str, Any]
    ) -> bool:
        """
        Send an approval request to the human review channel via Teams.

        Args:
            source_name: The source identifier needing approval.
            details: Contextual information about the source.

        Returns:
            True if the Teams notification was sent (or queued).
        """
        self._pending_approvals[source_name] = {
            "details": details,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }

        sent = send_approval_request(
            request_type="source_approval",
            details={
                "description": (
                    f"A new lead source '{source_name}' requires approval. "
                    f"It is not on the current allowlist."
                ),
                "requester": self.name,
                "source_name": source_name,
                "source_type": details.get("source_type", "unknown"),
                "reason": details.get("reason", "Unknown source provenance"),
                "review_sla_hours": details.get("review_sla_hours", 24),
                "approval_url": (
                    f"https://mcr-dashboard.example.com/sources/approve/{source_name}"
                ),
                "reject_url": (
                    f"https://mcr-dashboard.example.com/sources/reject/{source_name}"
                ),
            },
        )

        self.log_action(
            "request_approval",
            f"Approval request sent for source '{source_name}' (Teams sent={sent})",
            status="success" if sent else "pending",
            metadata={"source_name": source_name, "teams_sent": sent},
        )
        return sent

    # ------------------------------------------------------------------
    # process_approval_response
    # ------------------------------------------------------------------
    def process_approval_response(
        self, source_name: str, approved: bool
    ) -> Dict[str, Any]:
        """
        Process a human approval or rejection for a pending source.

        Updates the database record and clears the pending state.

        Args:
            source_name: The source being approved/rejected.
            approved: True to approve, False to reject.

        Returns:
            Result dict with updated source info.
        """
        source_record = self.source_repo.find_by_name(source_name)
        if source_record is None:
            self.log_action(
                "process_approval",
                f"Source '{source_name}' not found in database",
                status="failure",
            )
            return {"error": f"Source '{source_name}' not found in database"}

        new_risk = RiskLevel.MEDIUM.value if approved else RiskLevel.BLOCKED.value

        self.source_repo.update(
            source_record.source_id,
            approved_flag=approved,
            risk_level=new_risk,
        )
        self.session.commit()

        # Clear pending tracker
        self._pending_approvals.pop(source_name, None)

        action_word = "approved" if approved else "rejected"
        self.audit_repo.log(
            actor=self.name,
            entity_type="Source",
            entity_id=source_record.source_id,
            action="status_change",
            before_json=f'{{"approved_flag": false}}',
            after_json=f'{{"approved_flag": {str(approved).lower()}, "risk_level": "{new_risk}"}}',
        )
        self.session.commit()

        # Notify Teams
        send_teams_card(
            title=f"Source {action_word.title()}: {source_name}",
            facts=[
                {"title": "Source", "value": source_name},
                {"title": "Decision", "value": action_word.upper()},
                {"title": "Risk Level", "value": new_risk},
                {"title": "Decided At", "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")},
            ],
        )

        self.log_action(
            "process_approval",
            f"Source '{source_name}' {action_word} (risk={new_risk})",
            status="success",
            metadata={
                "source_name": source_name,
                "approved": approved,
                "risk_level": new_risk,
            },
        )

        return {
            "source_name": source_name,
            "approved": approved,
            "risk_level": new_risk,
            "action": action_word,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_deny_reason(self, source_type: str) -> str:
        """Get the denial reason for a blocked source type."""
        for rule in DENYLIST_RULES.get("source_types_denied", []):
            if rule["type"] == source_type:
                return rule.get("reason", "Denied per source policy")
        return "Denied per source policy"

    def _ensure_source_record(
        self,
        source_name: str,
        source_type: str,
        risk_level: str,
        approved: bool,
    ):
        """Find or create a Source record in the database."""
        record = self.source_repo.find_by_name(source_name)
        if record is None:
            record = self.source_repo.create(
                source_name=source_name,
                source_type=source_type,
                risk_level=risk_level,
                approved_flag=approved,
            )
            self.audit_repo.log(
                actor=self.name,
                entity_type="Source",
                entity_id=record.source_id,
                action="create",
                after_json=(
                    f'{{"source_name": "{source_name}", '
                    f'"source_type": "{source_type}", '
                    f'"risk_level": "{risk_level}", '
                    f'"approved_flag": {str(approved).lower()}}}'
                ),
            )
            self.session.commit()
        else:
            # Update if needed
            changed = False
            if record.approved_flag != approved:
                record.approved_flag = approved
                changed = True
            if record.risk_level != risk_level:
                record.risk_level = risk_level
                changed = True
            if changed:
                self.session.flush()
                self.session.commit()
        return record

    def is_domain_denied(self, domain: str) -> bool:
        """Check if a domain is on the denylist."""
        denied_domains = DENYLIST_RULES.get("domain_denylist", [])
        if not domain:
            return False
        return domain.lower().strip() in [d.lower() for d in denied_domains]

    def get_pending_approvals(self) -> Dict[str, Any]:
        """Return all currently pending approval requests."""
        return dict(self._pending_approvals)
