"""
MCRcore Growth Engine - Daily Orchestrator Agent

MASTER agent that runs the entire daily workflow end-to-end:

  1. Load source allowlist and suppression lists
  2. Run LeadDiscoveryAgent to acquire 50 new leads
  3. Run LeadEnrichmentAgent on new leads
  4. Run ERPSignalAgent on enriched leads
  5. Run OfferMatchingAgent on signal-detected leads
  6. Run ScoringAgent on all offer-matched leads
  7. Run MailboxProcessor to fetch and process replies
  8. Run ReplyClassificationAgent on new replies
  9. Run DailyRankingAgent to get top-5
 10. Run OutreachPersonalizationAgent on top-5
 11. Run ComplianceAgent gate on all outreach
 12. Send approved outreach via email_sender
 13. Run EscalationAgent on hot leads
 14. Run NurtureCadenceAgent to process due nurtures
 15. Calculate KPIs and send daily digest via Teams

Each step is wrapped in try/except with log_action() and continues on
failure.  Creates WorkflowJob records for end-to-end tracking.
"""

import json
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.agents.base_agent import BaseAgent
from src.utils.logger import get_agent_logger

from db.database import get_session
from db.repositories import (
    LeadRepository,
    OutreachRepository,
    ReplyRepository,
    SourceRepository,
    SuppressionRepository,
    WorkflowJobRepository,
)

# Agent imports (lazily referenced inside run to keep startup fast)
from src.agents.lead_discovery_agent import LeadDiscoveryAgent
from src.agents.lead_enrichment_agent import LeadEnrichmentAgent
from src.agents.erp_signal_agent import ERPSignalAgent
from src.agents.offer_matching_agent import OfferMatchingAgent
from src.agents.scoring_agent import ScoringAgent
from src.agents.reply_classification_agent import ReplyClassificationAgent
from src.agents.daily_ranking_agent import DailyRankingAgent
from src.agents.outreach_personalization_agent import OutreachPersonalizationAgent
from src.agents.compliance_agent import ComplianceAgent
from src.agents.escalation_agent import EscalationAgent

# Service imports
from src.services.mailbox_processor import MailboxProcessorService
from src.utils.email_sender import send_email
from src.utils.teams_notifier import send_daily_kpi

# Analytics
from src.skills.analytics_reporting import (
    calculate_daily_kpis,
    check_anomalies,
    format_kpi_summary,
    format_teams_kpi_card,
)


class DailyOrchestratorAgent(BaseAgent):
    """
    Master agent that orchestrates the entire MCRcore Growth Engine
    daily workflow.

    Creates a WorkflowJob record at start, executes each pipeline step
    sequentially with error isolation, and sends a daily KPI digest to
    Teams on completion.
    """

    def __init__(self):
        super().__init__(
            name="DailyOrchestratorAgent",
            description=(
                "Master orchestrator that runs the full daily Growth Engine "
                "pipeline: discovery -> enrichment -> scoring -> outreach -> "
                "reply processing -> escalation -> KPI reporting"
            ),
        )
        self.step_results: Dict[str, Any] = {}
        self.step_errors: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------
    def run(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the full daily workflow.

        Returns:
            Summary dict with per-step results, errors, and KPI data.
        """
        with get_session() as session:
            # Create WorkflowJob record
            job_repo = WorkflowJobRepository(session)
            job = job_repo.create(
                job_type="daily_orchestration",
                status="running",
                scheduled_at=datetime.now(timezone.utc),
                started_at=datetime.now(timezone.utc),
            )
            job_id = job.job_id
            session.commit()

            self.log_action(
                "workflow_start",
                f"Daily orchestration started — job {job_id[:8]}…",
                metadata={"job_id": job_id},
            )

            # ============================================================
            # Step 1: Load source allowlist and suppression lists
            # ============================================================
            approved_sources = []
            suppression_emails = []
            self._run_step(
                session, "step_01_load_lists",
                "Load source allowlist and suppression lists",
                lambda: self._step_load_lists(session),
            )

            # ============================================================
            # Step 2: LeadDiscoveryAgent — acquire 50 new leads
            # ============================================================
            self._run_step(
                session, "step_02_lead_discovery",
                "Discover new leads (target: 50)",
                lambda: self._step_lead_discovery(session),
            )

            # ============================================================
            # Step 3: LeadEnrichmentAgent — enrich new leads
            # ============================================================
            self._run_step(
                session, "step_03_lead_enrichment",
                "Enrich newly discovered leads",
                lambda: self._step_lead_enrichment(session),
            )

            # ============================================================
            # Step 4: ERPSignalAgent — detect ERP signals
            # ============================================================
            self._run_step(
                session, "step_04_erp_signals",
                "Detect ERP signals on enriched leads",
                lambda: self._step_erp_signals(session),
            )

            # ============================================================
            # Step 5: OfferMatchingAgent — match offers
            # ============================================================
            self._run_step(
                session, "step_05_offer_matching",
                "Match offers to signal-detected leads",
                lambda: self._step_offer_matching(session),
            )

            # ============================================================
            # Step 6: ScoringAgent — score all offer-matched leads
            # ============================================================
            self._run_step(
                session, "step_06_scoring",
                "Score all offer-matched leads",
                lambda: self._step_scoring(session),
            )

            # ============================================================
            # Step 7: MailboxProcessor — fetch and process replies
            # ============================================================
            self._run_step(
                session, "step_07_mailbox",
                "Fetch and process inbound replies",
                lambda: self._step_mailbox(session),
            )

            # ============================================================
            # Step 8: ReplyClassificationAgent — classify new replies
            # ============================================================
            self._run_step(
                session, "step_08_reply_classification",
                "Classify new replies",
                lambda: self._step_reply_classification(session),
            )

            # ============================================================
            # Step 9: DailyRankingAgent — get top-5 leads
            # ============================================================
            self._run_step(
                session, "step_09_daily_ranking",
                "Rank leads and select top-5 for outreach",
                lambda: self._step_daily_ranking(session),
            )

            # ============================================================
            # Step 10: OutreachPersonalizationAgent — personalize top-5
            # ============================================================
            self._run_step(
                session, "step_10_outreach_personalization",
                "Personalize outreach for top-5 leads",
                lambda: self._step_outreach_personalization(session),
            )

            # ============================================================
            # Step 11: ComplianceAgent — gate all outreach
            # ============================================================
            self._run_step(
                session, "step_11_compliance_gate",
                "Compliance gate on all pending outreach",
                lambda: self._step_compliance_gate(session),
            )

            # ============================================================
            # Step 12: Send approved outreach via email_sender
            # ============================================================
            self._run_step(
                session, "step_12_send_outreach",
                "Send approved outreach emails",
                lambda: self._step_send_outreach(session),
            )

            # ============================================================
            # Step 13: EscalationAgent — escalate hot leads
            # ============================================================
            self._run_step(
                session, "step_13_escalation",
                "Escalate hot leads to sales",
                lambda: self._step_escalation(session),
            )

            # ============================================================
            # Step 14: NurtureCadenceAgent — process due nurtures
            # ============================================================
            self._run_step(
                session, "step_14_nurture_cadence",
                "Process due nurture cadences",
                lambda: self._step_nurture_cadence(session),
            )

            # ============================================================
            # Step 15: KPIs and daily digest
            # ============================================================
            self._run_step(
                session, "step_15_kpi_digest",
                "Calculate KPIs and send daily digest",
                lambda: self._step_kpi_digest(session),
            )

            # ----------------------------------------------------------
            # Finalize workflow job
            # ----------------------------------------------------------
            total_steps = 15
            failed_steps = len(self.step_errors)
            succeeded_steps = total_steps - failed_steps

            summary = {
                "job_id": job_id,
                "total_steps": total_steps,
                "succeeded_steps": succeeded_steps,
                "failed_steps": failed_steps,
                "step_results": self.step_results,
                "step_errors": self.step_errors,
            }

            if failed_steps == 0:
                job_repo.mark_completed(
                    job_id,
                    result_json=json.dumps(summary, default=str),
                )
                self.log_action(
                    "workflow_complete",
                    f"Daily orchestration completed successfully — "
                    f"{succeeded_steps}/{total_steps} steps",
                    metadata=summary,
                )
            else:
                job_repo.mark_completed(
                    job_id,
                    result_json=json.dumps(summary, default=str),
                )
                self.log_action(
                    "workflow_complete_with_errors",
                    f"Daily orchestration completed with {failed_steps} errors — "
                    f"{succeeded_steps}/{total_steps} steps succeeded",
                    status="warning" if failed_steps < total_steps else "failure",
                    metadata=summary,
                )

            session.commit()
            return summary

    # ------------------------------------------------------------------
    # Step Runner (error-isolating wrapper)
    # ------------------------------------------------------------------
    def _run_step(
        self,
        session,
        step_name: str,
        description: str,
        step_fn,
    ) -> Optional[Any]:
        """
        Execute a single pipeline step with error isolation.

        Logs action, catches exceptions, records result or error.
        Always continues to the next step on failure.
        """
        self.log_action(
            step_name,
            f"Starting: {description}",
            status="pending",
        )

        try:
            result = step_fn()
            self.step_results[step_name] = result
            self.log_action(
                step_name,
                f"Completed: {description}",
                status="success",
                metadata={"result_summary": _safe_summary(result)},
            )
            session.commit()
            return result

        except Exception as e:
            error_detail = f"{type(e).__name__}: {e}"
            self.step_errors[step_name] = error_detail
            self.log_action(
                step_name,
                f"Failed: {description} — {error_detail}",
                status="failure",
                metadata={
                    "error": error_detail,
                    "traceback": traceback.format_exc(),
                },
            )
            try:
                session.rollback()
            except Exception:
                pass
            return None

    # ------------------------------------------------------------------
    # Individual Step Implementations
    # ------------------------------------------------------------------
    def _step_load_lists(self, session) -> Dict[str, Any]:
        """Step 1: Load source allowlist and suppression lists."""
        source_repo = SourceRepository(session)
        suppression_repo = SuppressionRepository(session)

        approved_sources = source_repo.get_approved()
        suppression_list = suppression_repo.list_all(limit=10000)

        result = {
            "approved_sources": len(approved_sources),
            "suppression_entries": len(suppression_list),
        }
        return result

    def _step_lead_discovery(self, session) -> Dict[str, Any]:
        """Step 2: Run LeadDiscoveryAgent to acquire 50 new leads."""
        agent = LeadDiscoveryAgent(session)
        result = agent.run(limit=50)
        return result or {"leads_discovered": 0}

    def _step_lead_enrichment(self, session) -> Dict[str, Any]:
        """Step 3: Run LeadEnrichmentAgent on new leads."""
        lead_repo = LeadRepository(session)
        new_leads = lead_repo.get_by_status("new", limit=100)
        lead_ids = [l.lead_id for l in new_leads]

        if not lead_ids:
            return {"leads_enriched": 0, "message": "No new leads to enrich"}

        agent = LeadEnrichmentAgent(session)
        result = agent.run(lead_ids=lead_ids)
        return result or {"leads_enriched": 0}

    def _step_erp_signals(self, session) -> Dict[str, Any]:
        """Step 4: Run ERPSignalAgent on enriched leads."""
        lead_repo = LeadRepository(session)
        enriched_leads = lead_repo.get_by_status("enriched", limit=100)
        lead_ids = [l.lead_id for l in enriched_leads]

        if not lead_ids:
            return {"signals_detected": 0, "message": "No enriched leads for ERP signals"}

        agent = ERPSignalAgent(session)
        result = agent.run(lead_ids=lead_ids)
        return result or {"signals_detected": 0}

    def _step_offer_matching(self, session) -> Dict[str, Any]:
        """Step 5: Run OfferMatchingAgent on signal-detected leads."""
        lead_repo = LeadRepository(session)
        # Leads with ERP signals have been moved to 'signal_detected' or
        # similar status — match on scored-ready statuses
        scored_ready = lead_repo.get_by_status("signal_detected", limit=100)
        lead_ids = [l.lead_id for l in scored_ready]

        if not lead_ids:
            return {"offers_matched": 0, "message": "No leads for offer matching"}

        agent = OfferMatchingAgent(session)
        result = agent.run(lead_ids=lead_ids)
        return result or {"offers_matched": 0}

    def _step_scoring(self, session) -> Dict[str, Any]:
        """Step 6: Run ScoringAgent on all offer-matched leads."""
        lead_repo = LeadRepository(session)
        offer_matched = lead_repo.get_by_status("offer_matched", limit=100)
        lead_ids = [l.lead_id for l in offer_matched]

        if not lead_ids:
            return {"leads_scored": 0, "message": "No leads for scoring"}

        agent = ScoringAgent(session)
        result = agent.run(lead_ids=lead_ids)
        return result or {"leads_scored": 0}

    def _step_mailbox(self, session) -> Dict[str, Any]:
        """Step 7: Run MailboxProcessor to fetch and process replies."""
        processor = MailboxProcessorService(session)
        result = processor.process_inbox()
        return result or {"replies_processed": 0}

    def _step_reply_classification(self, session) -> Dict[str, Any]:
        """Step 8: Run ReplyClassificationAgent on new replies."""
        reply_repo = ReplyRepository(session)
        unclassified = reply_repo.get_unclassified(limit=100)

        if not unclassified:
            return {"replies_classified": 0, "message": "No unclassified replies"}

        agent = ReplyClassificationAgent(session)
        result = agent.run(reply_ids=[r.reply_id for r in unclassified])
        return result or {"replies_classified": 0}

    def _step_daily_ranking(self, session) -> Dict[str, Any]:
        """Step 9: Run DailyRankingAgent to get top-5 leads."""
        agent = DailyRankingAgent(session)
        result = agent.run(top_n=5)
        # Store top_lead_ids for next steps
        if result and "ranked_leads" in result:
            self.step_results["_top_lead_ids"] = [
                r.get("lead_id") for r in result["ranked_leads"]
                if r.get("lead_id")
            ]
        return result or {"ranked_leads": []}

    def _step_outreach_personalization(self, session) -> Dict[str, Any]:
        """Step 10: Run OutreachPersonalizationAgent on top-5 leads."""
        top_lead_ids = self.step_results.get("_top_lead_ids", [])

        if not top_lead_ids:
            return {"outreach_drafted": 0, "message": "No top leads for outreach"}

        agent = OutreachPersonalizationAgent(session)
        result = agent.run(lead_ids=top_lead_ids)
        return result or {"outreach_drafted": 0}

    def _step_compliance_gate(self, session) -> Dict[str, Any]:
        """Step 11: Run ComplianceAgent gate on all pending outreach."""
        outreach_repo = OutreachRepository(session)
        pending = outreach_repo.get_pending_delivery(limit=100)

        if not pending:
            return {"compliance_checked": 0, "message": "No pending outreach"}

        agent = ComplianceAgent(session)
        result = agent.run(outreach_ids=[o.outreach_id for o in pending])
        return result or {"compliance_checked": 0}

    def _step_send_outreach(self, session) -> Dict[str, Any]:
        """Step 12: Send approved outreach via email_sender."""
        outreach_repo = OutreachRepository(session)
        # Get outreach that passed compliance (pending + compliance_passed)
        pending = outreach_repo.get_pending_delivery(limit=100)
        approved = [o for o in pending if o.compliance_passed]

        if not approved:
            return {"emails_sent": 0, "message": "No approved outreach to send"}

        sent_count = 0
        errors = []
        for outreach in approved:
            try:
                lead = outreach.lead
                if lead is None or lead.contact is None:
                    continue

                contact = lead.contact
                email_to = contact.email
                if not email_to:
                    continue

                success = send_email(
                    to_address=email_to,
                    subject=outreach.subject or "MCRcore Introduction",
                    body="",  # body from outreach template
                )
                if success:
                    outreach.delivery_status = "sent"
                    outreach.sent_at = datetime.now(timezone.utc)
                    sent_count += 1
                else:
                    outreach.delivery_status = "failed"
                    errors.append(outreach.outreach_id)

            except Exception as e:
                errors.append(f"{outreach.outreach_id}: {e}")

        session.flush()

        return {
            "emails_sent": sent_count,
            "errors": len(errors),
            "error_details": errors[:10],  # cap detail output
        }

    def _step_escalation(self, session) -> Dict[str, Any]:
        """Step 13: Run EscalationAgent on hot leads."""
        agent = EscalationAgent(session)
        result = agent.run()
        return result or {"escalated": 0}

    def _step_nurture_cadence(self, session) -> Dict[str, Any]:
        """Step 14: Process due nurture cadences."""
        from db.repositories import NurtureRepository

        nurture_repo = NurtureRepository(session)
        due_nurtures = nurture_repo.get_due(limit=100)

        if not due_nurtures:
            return {"nurtures_processed": 0, "message": "No due nurtures"}

        processed = 0
        for nurture in due_nurtures:
            try:
                lead = nurture.lead
                if lead is None or lead.contact is None:
                    nurture_repo.cancel_for_lead(nurture.lead_id)
                    continue

                if lead.opt_out_flag:
                    nurture_repo.cancel_for_lead(nurture.lead_id)
                    continue

                contact = lead.contact
                if not contact.email:
                    continue

                success = send_email(
                    to_address=contact.email,
                    subject=f"Following up — {nurture.stage or 'nurture'}",
                    body="",  # body from nurture template
                )

                if success:
                    nurture_repo.mark_sent(nurture.nurture_id)
                    processed += 1

            except Exception:
                continue

        session.flush()
        return {"nurtures_processed": processed, "total_due": len(due_nurtures)}

    def _step_kpi_digest(self, session) -> Dict[str, Any]:
        """Step 15: Calculate KPIs and send daily digest via Teams."""
        kpis = calculate_daily_kpis(session)

        # Log the text summary
        summary_text = format_kpi_summary(kpis)
        self.logger.info(f"Daily KPI Summary:\n{summary_text}")

        # Check for anomalies
        anomalies = check_anomalies(kpis)
        if anomalies:
            self.log_action(
                "anomaly_detected",
                f"{len(anomalies)} anomaly(ies) detected in daily KPIs",
                status="warning",
                metadata={"anomalies": anomalies},
            )

        # Format and send Teams card
        teams_card_data = format_teams_kpi_card(kpis)
        teams_sent = send_daily_kpi(teams_card_data)

        return {
            "kpis": kpis,
            "anomalies": anomalies,
            "teams_sent": teams_sent,
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _safe_summary(result: Any) -> Any:
    """Produce a JSON-safe summary of a step result (truncated)."""
    if result is None:
        return None
    if isinstance(result, dict):
        # Return top-level keys and scalar values, skip large nested data
        safe = {}
        for k, v in result.items():
            if k.startswith("_"):
                continue
            if isinstance(v, (str, int, float, bool, type(None))):
                safe[k] = v
            elif isinstance(v, list):
                safe[k] = f"[{len(v)} items]"
            elif isinstance(v, dict):
                safe[k] = f"{{{len(v)} keys}}"
            else:
                safe[k] = str(v)[:100]
        return safe
    return str(result)[:500]
