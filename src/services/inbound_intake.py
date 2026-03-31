"""
MCRcore Growth Engine - Inbound Form Intake Service

Processes inbound form submissions from mcrcore.com and referral
leads from Tallman Equipment Group (and other referral partners).

Creates leads with appropriate source_type and sends Teams
notifications on every new inbound lead.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.agents.lead_discovery_agent import LeadDiscoveryAgent
from src.utils.logger import setup_logger
from src.utils.teams_notifier import send_teams_card

logger = setup_logger("mcr_growth_engine.inbound_intake")

# Tallman referral identifiers for boosted priority
TALLMAN_REFERRAL_NAMES = {
    "tallman",
    "tallman equipment",
    "tallman equipment group",
}


class InboundIntakeService:
    """
    Processes mcrcore.com form submissions and partner referrals.
    Routes through LeadDiscoveryAgent for normalization, compliance,
    dedup, and record creation.
    """

    def __init__(self, session: Session):
        """
        Args:
            session: SQLAlchemy session.
        """
        self.session = session
        self.discovery_agent = LeadDiscoveryAgent(session)

    # ------------------------------------------------------------------
    # Inbound form submissions
    # ------------------------------------------------------------------
    def process_inbound_form(
        self, form_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a website form submission from mcrcore.com.

        Expected form_data keys:
            company_name, domain, industry, employee_count,
            contact_name, contact_title, contact_email, geography,
            message (optional), form_type (optional)

        Returns:
            Result dict from the discovery agent plus notification status.
        """
        logger.info(
            f"Processing inbound form: "
            f"{form_data.get('company_name', 'unknown')} / "
            f"{form_data.get('contact_email', 'unknown')}"
        )

        # Ensure source metadata
        form_data.setdefault("source_name", "mcrcore_inbound")
        form_data.setdefault("source_type", "inbound")

        # Process via discovery agent
        result = self.discovery_agent.discover_from_inbound(form_data)

        # Send Teams notification
        notification_sent = self._notify_inbound_lead(form_data, result)
        result["teams_notification_sent"] = notification_sent

        logger.info(
            f"Inbound form processed: status={result.get('status', 'unknown')}, "
            f"teams_notified={notification_sent}"
        )
        return result

    # ------------------------------------------------------------------
    # Referral submissions
    # ------------------------------------------------------------------
    def process_referral(
        self, referral_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a referral lead.

        Tallman Equipment Group referrals automatically receive boosted
        priority.  Other referral partners are processed normally.

        Expected referral_data keys:
            company_name, domain, industry, employee_count,
            contact_name, contact_title, contact_email, geography,
            referrer_name, referrer_company, referral_notes (optional)

        Returns:
            Result dict from the discovery agent plus notification status.
        """
        referrer_company = referral_data.get("referrer_company", "")
        referrer_name = referral_data.get("referrer_name", "")
        is_tallman = self._is_tallman_referral(referrer_company)

        logger.info(
            f"Processing referral from "
            f"{'Tallman Equipment Group (BOOSTED)' if is_tallman else referrer_company}: "
            f"{referral_data.get('company_name', 'unknown')}"
        )

        # Set source metadata
        if is_tallman:
            referral_data.setdefault("source_name", "tallman_referrals")
        else:
            referral_data.setdefault("source_name", f"referral_{self._slugify(referrer_company)}")
        referral_data.setdefault("source_type", "referral")

        # Process via discovery agent
        result = self.discovery_agent.discover_from_referral(referral_data)

        # Send Teams notification (with extra urgency for Tallman)
        notification_sent = self._notify_referral_lead(
            referral_data, result, is_tallman
        )
        result["teams_notification_sent"] = notification_sent
        result["is_tallman_referral"] = is_tallman

        logger.info(
            f"Referral processed: status={result.get('status', 'unknown')}, "
            f"tallman={is_tallman}, teams_notified={notification_sent}"
        )
        return result

    # ------------------------------------------------------------------
    # Teams Notifications
    # ------------------------------------------------------------------
    def _notify_inbound_lead(
        self, form_data: Dict[str, Any], result: Dict[str, Any]
    ) -> bool:
        """Send a Teams notification for a new inbound lead."""
        status = result.get("status", "unknown")
        company = form_data.get("company_name", "Unknown")
        contact = form_data.get("contact_name", "Unknown")
        email = form_data.get("contact_email", "Unknown")
        message = form_data.get("message", "")

        title = f"🔔 New Inbound Lead: {company}"
        if status == "skipped":
            title = f"⚠️ Inbound Lead Skipped: {company}"

        facts = [
            {"title": "Company", "value": company},
            {"title": "Contact", "value": f"{contact} ({email})"},
            {"title": "Industry", "value": form_data.get("industry", "N/A")},
            {"title": "Geography", "value": form_data.get("geography", "N/A")},
            {"title": "Status", "value": status.upper()},
        ]
        if message:
            facts.append({"title": "Message", "value": message[:200]})
        if result.get("recommended_offer"):
            facts.append(
                {"title": "Recommended Offer", "value": result["recommended_offer"]}
            )
        if result.get("reason"):
            facts.append({"title": "Detail", "value": result["reason"]})

        facts.append({
            "title": "Received At",
            "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        })

        return send_teams_card(title=title, facts=facts)

    def _notify_referral_lead(
        self,
        referral_data: Dict[str, Any],
        result: Dict[str, Any],
        is_tallman: bool,
    ) -> bool:
        """Send a Teams notification for a referral lead."""
        status = result.get("status", "unknown")
        company = referral_data.get("company_name", "Unknown")
        contact = referral_data.get("contact_name", "Unknown")
        email = referral_data.get("contact_email", "Unknown")
        referrer = referral_data.get("referrer_name", "Unknown")
        referrer_company = referral_data.get("referrer_company", "Unknown")
        notes = referral_data.get("referral_notes", "")

        priority_label = "⭐ TALLMAN PRIORITY" if is_tallman else "Referral"
        title = f"🤝 {priority_label}: {company}"
        if status == "skipped":
            title = f"⚠️ Referral Skipped: {company}"

        facts = [
            {"title": "Referred Company", "value": company},
            {"title": "Contact", "value": f"{contact} ({email})"},
            {"title": "Referrer", "value": f"{referrer} @ {referrer_company}"},
            {"title": "Industry", "value": referral_data.get("industry", "N/A")},
            {"title": "Geography", "value": referral_data.get("geography", "N/A")},
            {"title": "Priority", "value": "BOOSTED" if is_tallman else "Normal"},
            {"title": "Status", "value": status.upper()},
        ]
        if notes:
            facts.append({"title": "Referral Notes", "value": notes[:200]})
        if result.get("recommended_offer"):
            facts.append(
                {"title": "Recommended Offer", "value": result["recommended_offer"]}
            )

        facts.append({
            "title": "Received At",
            "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        })

        return send_teams_card(title=title, facts=facts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _is_tallman_referral(self, referrer_company: str) -> bool:
        """Check if the referrer is Tallman Equipment Group."""
        if not referrer_company:
            return False
        return referrer_company.strip().lower() in TALLMAN_REFERRAL_NAMES

    @staticmethod
    def _slugify(text: str) -> str:
        """Create a simple slug from text for source naming."""
        if not text:
            return "unknown"
        return (
            text.strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace(".", "")
            .replace(",", "")
            [:64]
        )
