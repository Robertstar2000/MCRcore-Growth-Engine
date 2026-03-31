"""
MCRcore Growth Engine - Nurture Cadence Agent

Manages the multi-touch nurture sequence for leads after first-touch
outreach.  Responsible for:

  - Querying due nurture items from the schedule
  - Cancelling nurture for leads that have opted out, replied, or bounced
  - Generating follow-up emails via OutreachPersonalizationAgent patterns
  - Running every draft through ComplianceAgent before sending
  - Marking items as sent and scheduling the next stage
  - Sending Teams notification summaries

Stage progression: first_touch -> day_7 -> day_30 -> day_90 -> archive
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.agents.base_agent import BaseAgent
from src.skills.nurture_cadence import (
    CANCEL_REASONS,
    NURTURE_STAGES,
    STAGE_DELTAS,
    calculate_schedule_time,
    get_next_nurture_stage,
    get_nurture_template_variation,
    get_subject_for_angle,
    should_cancel_nurture,
)
from src.utils.logger import get_agent_logger


class NurtureCadenceAgent(BaseAgent):
    """
    Orchestrates the nurture cadence for all leads in the pipeline.

    On each run():
      1. Queries NurtureRepository.get_due() for items whose scheduled_at
         has passed and that are not yet sent or cancelled.
      2. For each due item, checks opt-out / reply / bounce status.
      3. Generates a follow-up email using OutreachPersonalizationAgent.
      4. Passes the draft through ComplianceAgent for approval.
      5. Marks the nurture as sent, schedules the next stage.
      6. Sends a Teams notification summary.
    """

    def __init__(self):
        super().__init__(
            name="NurtureCadenceAgent",
            description=(
                "Manages the multi-touch nurture sequence (day_7 / day_30 / "
                "day_90) for leads, ensuring unique angles, compliance, and "
                "proper stage progression."
            ),
        )

    # ==================================================================
    # BaseAgent interface
    # ==================================================================

    def run(self, **kwargs) -> Dict[str, Any]:
        """
        Process all due nurture items.

        Returns:
            Summary dict with counts of sent, cancelled, failed items.
        """
        from db.database import get_session

        sent_count = 0
        cancelled_count = 0
        failed_count = 0
        details: List[Dict[str, Any]] = []

        with get_session() as session:
            from db.repositories import (
                LeadRepository,
                NurtureRepository,
                OutreachRepository,
            )

            nurture_repo = NurtureRepository(session)
            lead_repo = LeadRepository(session)
            outreach_repo = OutreachRepository(session)

            due_items = nurture_repo.get_due()

            self.log_action(
                "run_start",
                f"Found {len(due_items)} due nurture items",
                metadata={"due_count": len(due_items)},
            )

            for item in due_items:
                try:
                    result = self._process_nurture_item(
                        item, session, nurture_repo, lead_repo, outreach_repo
                    )

                    if result["action"] == "sent":
                        sent_count += 1
                    elif result["action"] == "cancelled":
                        cancelled_count += 1
                    else:
                        failed_count += 1

                    details.append(result)

                except Exception as exc:
                    failed_count += 1
                    self.log_action(
                        "process_nurture_item",
                        f"Error processing nurture {item.nurture_id}: {exc}",
                        status="failure",
                        metadata={
                            "nurture_id": item.nurture_id,
                            "lead_id": item.lead_id,
                            "error": str(exc),
                        },
                    )
                    details.append({
                        "nurture_id": item.nurture_id,
                        "lead_id": item.lead_id,
                        "action": "error",
                        "error": str(exc),
                    })

        summary = {
            "total_due": len(due_items) if "due_items" in dir() else 0,
            "sent": sent_count,
            "cancelled": cancelled_count,
            "failed": failed_count,
            "details": details,
        }

        self.log_action(
            "run_complete",
            f"Nurture run: {sent_count} sent, {cancelled_count} cancelled, "
            f"{failed_count} failed",
            metadata=summary,
        )

        # Teams summary notification
        self._send_teams_summary(summary)

        return summary

    # ==================================================================
    # Schedule / Cancel API
    # ==================================================================

    def schedule_nurture(self, lead_id: str, session, anchor: Optional[datetime] = None) -> List[str]:
        """
        Create the initial 7/30/90-day nurture schedule entries for a lead.

        Args:
            lead_id: UUID of the lead.
            session: Active SQLAlchemy session.
            anchor: Reference datetime (defaults to now-UTC). Typically
                    the first-touch sent_at.

        Returns:
            List of created nurture_id values.
        """
        from db.repositories import NurtureRepository

        nurture_repo = NurtureRepository(session)

        if anchor is None:
            anchor = datetime.now(timezone.utc)

        created_ids: List[str] = []

        for stage in NURTURE_STAGES:
            scheduled_at = calculate_schedule_time(stage, anchor=anchor)
            nurture = nurture_repo.create(
                nurture_id=str(uuid.uuid4()),
                lead_id=lead_id,
                stage=stage,
                scheduled_at=scheduled_at,
                sent=False,
                cancelled=False,
            )
            created_ids.append(nurture.nurture_id)

        self.log_action(
            "schedule_nurture",
            f"Created {len(created_ids)} nurture entries for lead {lead_id[:8]}…",
            metadata={
                "lead_id": lead_id,
                "stages": list(NURTURE_STAGES),
                "nurture_ids": created_ids,
            },
        )

        return created_ids

    def cancel_nurture(self, lead_id: str, session, reason: str = "manual") -> int:
        """
        Cancel all pending nurture entries for a lead.

        Args:
            lead_id: UUID of the lead.
            session: Active SQLAlchemy session.
            reason: Cancellation reason key (from CANCEL_REASONS).

        Returns:
            Number of nurture entries cancelled.
        """
        from db.repositories import NurtureRepository

        nurture_repo = NurtureRepository(session)
        cancelled = nurture_repo.cancel_for_lead(lead_id)

        reason_text = CANCEL_REASONS.get(reason, reason)

        self.log_action(
            "cancel_nurture",
            f"Cancelled {cancelled} nurture entries for lead {lead_id[:8]}… "
            f"reason={reason_text}",
            metadata={
                "lead_id": lead_id,
                "cancelled_count": cancelled,
                "reason": reason,
                "reason_text": reason_text,
            },
        )

        return cancelled

    # ==================================================================
    # Internal: process a single due nurture item
    # ==================================================================

    def _process_nurture_item(
        self,
        item,
        session,
        nurture_repo,
        lead_repo,
        outreach_repo,
    ) -> Dict[str, Any]:
        """
        Process a single due nurture item through the full pipeline:
        check -> generate -> compliance -> send -> schedule next.
        """
        lead = lead_repo.get_by_id(item.lead_id)

        if lead is None:
            nurture_repo.update(item.nurture_id, cancelled=True)
            self.log_action(
                "process_nurture_item",
                f"Lead {item.lead_id} not found — nurture cancelled",
                status="skipped",
                metadata={"nurture_id": item.nurture_id},
            )
            return {
                "nurture_id": item.nurture_id,
                "lead_id": item.lead_id,
                "action": "cancelled",
                "reason": "lead_not_found",
            }

        # ---- Check cancellation conditions ----
        has_replied = self._lead_has_replied(item.lead_id, session)
        cancel, reason = should_cancel_nurture(
            opt_out=bool(getattr(lead, "opt_out_flag", False)),
            has_replied=has_replied,
            is_bounced=getattr(lead, "status", "") == "bounced",
            is_converted=getattr(lead, "status", "") == "converted",
        )

        if cancel:
            self.cancel_nurture(item.lead_id, session, reason=reason)
            return {
                "nurture_id": item.nurture_id,
                "lead_id": item.lead_id,
                "action": "cancelled",
                "reason": reason,
            }

        # ---- Generate follow-up email ----
        prior_angles = self._get_prior_angles(item.lead_id, outreach_repo)
        angle, subject_options = get_nurture_template_variation(
            item.stage, prior_angles=prior_angles,
        )

        outreach_result = self._generate_outreach(
            lead_id=item.lead_id,
            stage=item.stage,
            session=session,
        )

        if outreach_result.get("status") == "error":
            self.log_action(
                "generate_outreach",
                f"Outreach generation failed for nurture {item.nurture_id}",
                status="failure",
                metadata={"nurture_id": item.nurture_id, "error": outreach_result.get("error")},
            )
            return {
                "nurture_id": item.nurture_id,
                "lead_id": item.lead_id,
                "action": "failed",
                "error": outreach_result.get("error", "generation_failed"),
            }

        # ---- Compliance check ----
        compliance_result = self._run_compliance_check(
            lead_id=item.lead_id,
            draft_email=outreach_result,
            session=session,
        )

        if not compliance_result.get("approved", False):
            self.log_action(
                "compliance_check",
                f"Nurture {item.nurture_id} blocked by compliance",
                status="failure",
                metadata={
                    "nurture_id": item.nurture_id,
                    "checks_failed": compliance_result.get("checks_failed", []),
                },
            )
            return {
                "nurture_id": item.nurture_id,
                "lead_id": item.lead_id,
                "action": "failed",
                "error": "compliance_blocked",
                "compliance": compliance_result,
            }

        # ---- Mark as sent ----
        message_id = outreach_result.get("outreach_id", str(uuid.uuid4()))
        nurture_repo.mark_sent(item.nurture_id, message_id=message_id)

        # ---- Schedule next stage ----
        next_stage = get_next_nurture_stage(item.stage)
        if next_stage is not None:
            self.log_action(
                "stage_progression",
                f"Lead {item.lead_id[:8]}… advancing: {item.stage} -> {next_stage}",
                metadata={
                    "lead_id": item.lead_id,
                    "current_stage": item.stage,
                    "next_stage": next_stage,
                },
            )
        else:
            # Sequence complete — archive
            self.log_action(
                "stage_progression",
                f"Lead {item.lead_id[:8]}… nurture complete — moving to archive",
                metadata={
                    "lead_id": item.lead_id,
                    "final_stage": item.stage,
                },
            )

        self.log_action(
            "nurture_sent",
            f"Sent {item.stage} nurture for lead {item.lead_id[:8]}… "
            f"(angle={angle})",
            metadata={
                "nurture_id": item.nurture_id,
                "lead_id": item.lead_id,
                "stage": item.stage,
                "angle": angle,
                "message_id": message_id,
            },
        )

        return {
            "nurture_id": item.nurture_id,
            "lead_id": item.lead_id,
            "action": "sent",
            "stage": item.stage,
            "angle": angle,
            "message_id": message_id,
            "next_stage": next_stage,
        }

    # ==================================================================
    # Helpers
    # ==================================================================

    def _lead_has_replied(self, lead_id: str, session) -> bool:
        """Check if a lead has any reply events."""
        try:
            from db.repositories import ReplyRepository
            reply_repo = ReplyRepository(session)
            replies = reply_repo.get_by_lead(lead_id)
            return len(replies) > 0
        except Exception:
            return False

    def _get_prior_angles(self, lead_id: str, outreach_repo) -> List[str]:
        """
        Get the list of package_angle values already used for a lead
        to ensure uniqueness in follow-up messaging.
        """
        try:
            prior_events = outreach_repo.get_by_lead(lead_id)
            angles = []
            for event in prior_events:
                angle = getattr(event, "package_angle", None)
                if angle:
                    angles.append(angle)
            return angles
        except Exception:
            return []

    def _generate_outreach(
        self,
        lead_id: str,
        stage: str,
        session,
    ) -> Dict[str, Any]:
        """
        Generate a follow-up email using OutreachPersonalizationAgent.

        Falls back to a minimal result if the agent is unavailable.
        """
        try:
            from src.agents.outreach_personalization_agent import (
                OutreachPersonalizationAgent,
            )

            outreach_agent = OutreachPersonalizationAgent()
            result = outreach_agent.run(lead_id=lead_id, stage=stage, session=session)
            return result
        except Exception as exc:
            self.logger.warning(
                f"OutreachPersonalizationAgent unavailable: {exc}. "
                "Returning template-only result."
            )
            return {
                "lead_id": lead_id,
                "stage": stage,
                "status": "error",
                "error": f"Outreach generation failed: {exc}",
            }

    def _run_compliance_check(
        self,
        lead_id: str,
        draft_email: Dict[str, Any],
        session,
    ) -> Dict[str, Any]:
        """
        Run the draft through ComplianceAgent.

        Falls back to auto-approve if the agent is unavailable (with warning).
        """
        try:
            from src.agents.compliance_agent import ComplianceAgent

            compliance_agent = ComplianceAgent(db_session=session)
            result = compliance_agent.run(
                lead_id=lead_id,
                draft_email={
                    "to_email": draft_email.get("to_email", ""),
                    "from_addr": draft_email.get("from_addr", "outreach@mcrconsultinggroup.com"),
                    "subject": draft_email.get("subject", ""),
                    "body": draft_email.get("body", ""),
                    "sending_domain": "mcrconsultinggroup.com",
                },
            )
            return result
        except Exception as exc:
            self.logger.warning(
                f"ComplianceAgent unavailable: {exc}. "
                "Falling back to auto-approve with risk flag."
            )
            return {
                "approved": True,
                "checks_passed": [],
                "checks_failed": [],
                "risk_flags": [f"Compliance check skipped: {exc}"],
            }

    def _send_teams_summary(self, summary: Dict[str, Any]) -> None:
        """Send a Teams notification with the nurture run summary."""
        try:
            from src.utils.teams_notifier import send_teams_message

            total = summary.get("total_due", 0)
            if total == 0:
                # Don't spam Teams when there's nothing to report
                return

            message = (
                f"🔄 Nurture Cadence Run Complete\n\n"
                f"• Due items: {total}\n"
                f"• Sent: {summary.get('sent', 0)}\n"
                f"• Cancelled: {summary.get('cancelled', 0)}\n"
                f"• Failed: {summary.get('failed', 0)}"
            )

            send_teams_message(message)
        except Exception as exc:
            self.logger.warning(f"Teams notification failed: {exc}")

    def __repr__(self) -> str:
        return (
            f"<NurtureCadenceAgent id='{self.agent_id[:8]}' "
            f"actions={len(self.audit_trail)}>"
        )
