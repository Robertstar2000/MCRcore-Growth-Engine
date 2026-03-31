"""
MCRcore Growth Engine - Opportunity Escalation Agent

Prepares human-ready handoff packets for MCRcore sales when a lead
shows strong buying intent. Builds complete summary with company info,
scores, communication history, and recommended actions. Sends both
an internal escalation email and a Teams alert.
"""

import json
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.skills.escalation_packet import (
    build_action_checklist,
    build_escalation_summary,
    estimate_opportunity_value,
    format_communication_timeline,
)
from src.utils.teams_notifier import send_escalation_alert
from db.repositories import (
    CompanyRepository,
    ContactRepository,
    EnrichmentRepository,
    LeadRepository,
    OpportunityRepository,
    OutreachRepository,
    ReplyRepository,
    ScoreRepository,
    AuditRepository,
)

# Escalation email config (from environment)
ESCALATION_EMAIL = os.getenv("ESCALATION_EMAIL", "PLACEHOLDER_sales@mcrcore.com")
SMTP_HOST = os.getenv("SMTP_HOST", "PLACEHOLDER_smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "PLACEHOLDER_smtp-user")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "PLACEHOLDER_smtp-password")
SMTP_FROM = os.getenv("SMTP_FROM", "growth-engine@mcrcore.com")


class EscalationAgent(BaseAgent):
    """
    Prepares and delivers human-ready opportunity handoff packets
    to the MCRcore sales team.
    """

    def __init__(self, session: Session):
        super().__init__(
            name="escalation-agent",
            description="Builds escalation packets and notifies sales team",
        )
        self.session = session
        self.lead_repo = LeadRepository(session)
        self.company_repo = CompanyRepository(session)
        self.contact_repo = ContactRepository(session)
        self.enrichment_repo = EnrichmentRepository(session)
        self.score_repo = ScoreRepository(session)
        self.outreach_repo = OutreachRepository(session)
        self.reply_repo = ReplyRepository(session)
        self.opportunity_repo = OpportunityRepository(session)
        self.audit_repo = AuditRepository(session)

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------
    def run(self, lead_ids: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Escalate one or more leads. If no lead_ids given, finds all leads
        with escalation_pending substatus.

        Returns summary dict of escalation results.
        """
        if lead_ids is None:
            leads = self.lead_repo.get_by_status("qualified", limit=100)
            lead_ids = [
                l.lead_id for l in leads
                if l.substatus == "escalation_pending"
            ]

        results = []
        for lead_id in lead_ids:
            try:
                result = self.escalate_opportunity(lead_id)
                results.append(result)
            except Exception as e:
                self.log_action(
                    "escalate_opportunity",
                    f"Failed to escalate lead {lead_id}: {e}",
                    status="failure",
                    metadata={"lead_id": lead_id, "error": str(e)},
                )
                results.append({"lead_id": lead_id, "error": str(e)})

        summary = {
            "total_processed": len(results),
            "successful": sum(1 for r in results if "error" not in r),
            "failed": sum(1 for r in results if "error" in r),
            "escalations": results,
        }

        self.log_action(
            "run_complete",
            f"Escalated {summary['successful']}/{summary['total_processed']} leads",
            metadata=summary,
        )
        return summary

    # ------------------------------------------------------------------
    # Core Escalation
    # ------------------------------------------------------------------
    def escalate_opportunity(self, lead_id: str) -> Dict[str, Any]:
        """
        Build and deliver a complete escalation packet for a lead.

        Steps:
          1. Load all lead data
          2. Build summary, timeline, and action recommendation
          3. Estimate value
          4. Create Opportunity record
          5. Send escalation email
          6. Send Teams escalation alert
          7. Mark lead as escalated

        Returns dict with opportunity details and delivery status.
        """
        # Load lead and all related data
        lead = self.lead_repo.get_by_id(lead_id)
        if lead is None:
            raise ValueError(f"Lead not found: {lead_id}")

        lead_data = self._load_lead_data(lead)
        score_data = self._load_score_data(lead_id)

        # Build summary components
        summary_data = self.build_summary(lead_data)
        timeline_events = self.build_communication_timeline(lead_id)
        action_rec = self.build_action_recommendation(lead_data, score_data)

        # Estimate value
        package_id = lead.recommended_offer or "total_plan"
        employee_band = lead_data.get("employee_band")
        value_estimate = estimate_opportunity_value(package_id, employee_band)

        # Build full summary text
        opportunity_data = {
            **summary_data,
            "recommended_package": package_id,
            "estimated_value_band": value_estimate["value_band_label"],
            "estimated_margin_band": value_estimate["margin_band"],
        }

        # Get trigger reply text
        trigger_reply = ""
        replies = self.reply_repo.get_by_lead(lead_id)
        if replies:
            latest_reply = replies[0]  # sorted desc
            trigger_reply = latest_reply.raw_text or ""
        opportunity_data["trigger_reply_text"] = trigger_reply[:1000]

        full_summary = build_escalation_summary(
            opportunity_data, timeline_events, action_rec
        )

        # Create Opportunity record
        opportunity = self.opportunity_repo.create(
            lead_id=lead_id,
            recommended_package=package_id,
            estimated_value_band=value_estimate["value_band_label"],
            estimated_margin_band=value_estimate["margin_band"],
            summary=full_summary[:4000],  # truncate for DB
            escalated_to=ESCALATION_EMAIL,
            escalated_at=datetime.now(timezone.utc),
            status="open",
        )

        # Send escalation email
        email_sent = self.send_escalation_email(opportunity, full_summary, lead_data)

        # Send Teams escalation alert
        teams_sent = self.send_teams_escalation(opportunity, lead_data, score_data, value_estimate)

        # Mark lead as escalated
        self.lead_repo.update(
            lead_id,
            status="escalated",
            substatus="opportunity_created",
            last_processed_at=datetime.now(timezone.utc),
        )

        # Audit trail
        self.audit_repo.log(
            actor=self.name,
            entity_type="opportunity",
            entity_id=opportunity.opportunity_id,
            action="create",
            after_json=json.dumps({
                "lead_id": lead_id,
                "package": package_id,
                "value_band": value_estimate["value_band_label"],
                "email_sent": email_sent,
                "teams_sent": teams_sent,
            }),
        )

        result = {
            "lead_id": lead_id,
            "opportunity_id": opportunity.opportunity_id,
            "recommended_package": package_id,
            "estimated_value": value_estimate,
            "email_sent": email_sent,
            "teams_sent": teams_sent,
        }

        self.log_action(
            "escalate_opportunity",
            f"Opportunity {opportunity.opportunity_id[:8]}… created for lead {lead_id[:8]}…",
            metadata=result,
        )

        self.session.commit()
        return result

    # ------------------------------------------------------------------
    # Summary Building
    # ------------------------------------------------------------------
    def build_summary(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a summary data dict from lead, company, contact, and score data.

        Args:
            lead_data: Dict with all related entity fields.

        Returns:
            Dict ready for template formatting.
        """
        return {
            "company_name": lead_data.get("company_name", "Unknown"),
            "domain": lead_data.get("domain", "N/A"),
            "industry": lead_data.get("industry", "N/A"),
            "employee_band": lead_data.get("employee_band", "N/A"),
            "geography": lead_data.get("geography", "N/A"),
            "website_url": lead_data.get("website_url", "N/A"),
            "contact_name": lead_data.get("contact_name", "Unknown"),
            "contact_title": lead_data.get("contact_title", "N/A"),
            "contact_email": lead_data.get("contact_email", "N/A"),
            "profile_url": lead_data.get("profile_url", "N/A"),
            "fit_score": lead_data.get("fit_score", "N/A"),
            "need_score": lead_data.get("need_score", "N/A"),
            "engagement_score": lead_data.get("engagement_score", "N/A"),
            "package_fit_score": lead_data.get("package_fit_score", "N/A"),
            "sales_probability": lead_data.get("sales_probability", "N/A"),
            "priority_tier": lead_data.get("priority_tier", "N/A"),
            "margin_band": lead_data.get("margin_band", "N/A"),
            "recommended_entry_cta": lead_data.get("recommended_entry_cta", "N/A"),
        }

    def build_communication_timeline(self, lead_id: str) -> List[Dict[str, Any]]:
        """
        Build a chronological list of communication events for a lead.

        Args:
            lead_id: The lead to build the timeline for.

        Returns:
            List of event dicts with timestamp, event_type, summary.
        """
        events = []

        # Outreach events
        outreach_events = self.outreach_repo.get_by_lead(lead_id)
        for oe in outreach_events:
            events.append({
                "timestamp": oe.sent_at or datetime.now(timezone.utc),
                "event_type": "outreach_sent",
                "summary": (
                    f"Stage: {oe.stage or 'N/A'} | "
                    f"Subject: {oe.subject or 'N/A'} | "
                    f"Delivery: {oe.delivery_status or 'N/A'}"
                ),
            })
            if oe.open_status:
                events.append({
                    "timestamp": oe.sent_at or datetime.now(timezone.utc),
                    "event_type": "email_opened",
                    "summary": f"Opened: {oe.subject or 'N/A'}",
                })
            if oe.click_status:
                events.append({
                    "timestamp": oe.sent_at or datetime.now(timezone.utc),
                    "event_type": "link_clicked",
                    "summary": f"Clicked link in: {oe.subject or 'N/A'}",
                })

        # Reply events
        reply_events = self.reply_repo.get_by_lead(lead_id)
        for re_event in reply_events:
            preview = (re_event.raw_text or "")[:100]
            events.append({
                "timestamp": re_event.received_at or datetime.now(timezone.utc),
                "event_type": "reply_received",
                "summary": (
                    f"Classified: {re_event.classified_as or 'pending'} | "
                    f"Preview: {preview}"
                ),
            })

        # Sort chronologically
        events.sort(key=lambda e: e["timestamp"] if isinstance(e["timestamp"], datetime) else datetime.min)

        return events

    def build_action_recommendation(
        self,
        lead_data: Dict[str, Any],
        score_data: Dict[str, Any],
    ) -> str:
        """
        Build an action recommendation checklist based on lead and score data.

        Args:
            lead_data: Combined lead/company/contact data.
            score_data: Latest score snapshot data.

        Returns:
            Formatted action recommendation string.
        """
        probability = score_data.get("sales_probability", 0)
        tier = score_data.get("priority_tier", "tier4")
        package = lead_data.get("recommended_offer", "total_plan")
        contact_name = lead_data.get("contact_name", "the prospect")

        # Determine primary action based on context
        if probability >= 80:
            primary_action = (
                f"Call {contact_name} within 2 hours — high probability ({probability}%)"
            )
            sla = "2 hours"
        elif probability >= 60:
            primary_action = (
                f"Send personalized follow-up email to {contact_name} — "
                f"warm prospect ({probability}%)"
            )
            sla = "4 hours"
        else:
            primary_action = (
                f"Review opportunity and send introductory follow-up to {contact_name}"
            )
            sla = "24 hours"

        additional_actions = [
            f"Prepare {package} proposal materials",
            "Research company on LinkedIn for recent activity",
            "Check if any existing MCRcore relationship exists",
        ]

        talking_points = [
            f"Reference their specific reply and expressed interest",
            f"Highlight {package} benefits for their industry ({lead_data.get('industry', 'N/A')})",
            f"Offer a no-obligation discovery call or assessment",
            f"Mention relevant case studies for similar companies",
        ]

        return build_action_checklist(
            primary_action=primary_action,
            additional_actions=additional_actions,
            response_sla=sla,
            follow_up_deadline="48 hours",
            talking_points=talking_points,
        )

    # ------------------------------------------------------------------
    # Delivery Methods
    # ------------------------------------------------------------------
    def send_escalation_email(
        self,
        opportunity,
        full_summary: str,
        lead_data: Dict[str, Any],
    ) -> bool:
        """
        Send escalation email to the configured sales inbox.

        Args:
            opportunity: Opportunity ORM object.
            full_summary: Full formatted escalation summary text.
            lead_data: Lead data dict for subject line.

        Returns:
            True if email was sent successfully.
        """
        if "PLACEHOLDER" in ESCALATION_EMAIL or "PLACEHOLDER" in SMTP_HOST:
            self.logger.warning(
                "Escalation email not configured (PLACEHOLDER values) — skipping send"
            )
            self.log_action(
                "send_escalation_email",
                "Skipped — SMTP not configured",
                status="skipped",
                metadata={"opportunity_id": opportunity.opportunity_id},
            )
            return False

        company = lead_data.get("company_name", "Unknown")
        subject = (
            f"🚨 MCRcore Escalation: {company} — "
            f"Opportunity {opportunity.opportunity_id[:8]}"
        )

        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = ESCALATION_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(full_summary, "plain", "utf-8"))

        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM, [ESCALATION_EMAIL], msg.as_string())

            self.log_action(
                "send_escalation_email",
                f"Escalation email sent to {ESCALATION_EMAIL}",
                metadata={
                    "opportunity_id": opportunity.opportunity_id,
                    "to": ESCALATION_EMAIL,
                },
            )
            return True

        except Exception as e:
            self.log_action(
                "send_escalation_email",
                f"Failed to send escalation email: {e}",
                status="failure",
                metadata={
                    "opportunity_id": opportunity.opportunity_id,
                    "error": str(e),
                },
            )
            return False

    def send_teams_escalation(
        self,
        opportunity,
        lead_data: Dict[str, Any],
        score_data: Dict[str, Any],
        value_estimate: Dict[str, Any],
    ) -> bool:
        """
        Send escalation alert to Teams with full summary.

        Args:
            opportunity: Opportunity ORM object.
            lead_data: Lead data dict.
            score_data: Score snapshot data.
            value_estimate: Value estimation dict.

        Returns:
            True if Teams notification was sent successfully.
        """
        company = lead_data.get("company_name", "Unknown")
        contact = lead_data.get("contact_name", "Unknown")
        email = lead_data.get("contact_email", "N/A")

        return send_escalation_alert({
            "company": company,
            "contact": f"{contact} ({email})",
            "value": value_estimate.get("value_band_label", "N/A"),
            "reason": (
                f"Positive reply detected — "
                f"Probability: {score_data.get('sales_probability', 'N/A')}%, "
                f"Tier: {score_data.get('priority_tier', 'N/A')}"
            ),
            "recommended_action": (
                f"Review {opportunity.recommended_package or 'N/A'} opportunity — "
                f"Est. {value_estimate.get('value_band_label', 'N/A')}"
            ),
        })

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------
    def _load_lead_data(self, lead) -> Dict[str, Any]:
        """Load all related data for a lead into a flat dict."""
        data = {
            "lead_id": lead.lead_id,
            "status": lead.status,
            "substatus": lead.substatus,
            "recommended_offer": lead.recommended_offer,
            "recommended_entry_cta": lead.recommended_entry_cta or "N/A",
        }

        # Company info
        if lead.company:
            c = lead.company
            data.update({
                "company_name": c.company_name or "Unknown",
                "domain": c.domain or "N/A",
                "industry": c.industry or "N/A",
                "employee_band": c.employee_band or "N/A",
                "geography": c.geography or "N/A",
                "website_url": c.website_url or "N/A",
            })

        # Contact info
        if lead.contact:
            ct = lead.contact
            data.update({
                "contact_name": ct.full_name or "Unknown",
                "contact_title": ct.title or "N/A",
                "contact_email": ct.email or "N/A",
                "profile_url": ct.profile_url or "N/A",
            })

        # Enrichment info
        enrichment = self.enrichment_repo.get_by_lead(lead.lead_id)
        if enrichment:
            data.update({
                "operational_pain": enrichment.operational_pain_summary or "",
                "it_pain_points": enrichment.it_pain_points or "",
                "company_summary": enrichment.company_summary or "",
            })

        # Score info (latest)
        score = self.score_repo.get_latest_for_lead(lead.lead_id)
        if score:
            data.update({
                "fit_score": score.fit_score,
                "need_score": score.need_score,
                "engagement_score": score.engagement_score,
                "package_fit_score": score.package_fit_score,
                "sales_probability": score.sales_probability,
                "priority_tier": score.priority_tier or "N/A",
                "margin_band": score.margin_band or "N/A",
            })

        return data

    def _load_score_data(self, lead_id: str) -> Dict[str, Any]:
        """Load latest score snapshot as a plain dict."""
        score = self.score_repo.get_latest_for_lead(lead_id)
        if score is None:
            return {
                "fit_score": 0,
                "need_score": 0,
                "engagement_score": 0,
                "package_fit_score": 0,
                "sales_probability": 0,
                "priority_tier": "N/A",
                "margin_band": "N/A",
            }
        return {
            "fit_score": score.fit_score,
            "need_score": score.need_score,
            "engagement_score": score.engagement_score,
            "package_fit_score": score.package_fit_score,
            "sales_probability": score.sales_probability,
            "priority_tier": score.priority_tier or "N/A",
            "margin_band": score.margin_band or "N/A",
        }
