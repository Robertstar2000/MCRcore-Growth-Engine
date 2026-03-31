"""
MCRcore Growth Engine - Daily Ranking Agent

Queries all scored leads, applies override rules, ranks them,
and returns the top 5 highest-probability leads for daily outreach.
Sends a top-5 summary to Microsoft Teams.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.skills.lead_scoring import (
    apply_override_rules,
    tie_break_leads,
)
from config.geo_routing import get_geo_zone, MIDWEST_STATE_CODES
from config.service_catalog import SERVICES
from db.repositories import (
    CompanyRepository,
    ContactRepository,
    LeadRepository,
    ScoreRepository,
    SignalRepository,
    SuppressionRepository,
)
from src.utils.teams_notifier import send_teams_card


def _parse_state_code(geography: Optional[str]) -> str:
    """Extract state code from geography field."""
    if not geography:
        return ""
    parts = geography.replace(",", " ").split()
    for part in parts:
        cleaned = part.strip().upper()
        if len(cleaned) == 2 and cleaned.isalpha():
            return cleaned
    return ""


class DailyRankingAgent(BaseAgent):
    """
    Agent that produces the daily top-5 lead list for outreach.

    Workflow:
      1. Query all leads with recent ScoreSnapshots
      2. Apply override rules (suppress opt-outs, boost referrals, etc.)
      3. Rank by sales_probability with tie-break logic
      4. Select top 5
      5. Send summary to Teams
    """

    def __init__(self):
        super().__init__(
            name="DailyRankingAgent",
            description="Produces daily top-5 ranked leads for outreach",
        )

    def run(self, session: Session, n: int = 5) -> List[Dict[str, Any]]:
        """Primary entry point. Get the daily top-N leads."""
        return self.get_daily_top5(session, n=n)

    def get_daily_top5(
        self,
        session: Session,
        n: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Full daily ranking pipeline.

        1. Query scored leads
        2. Apply overrides
        3. Rank
        4. Select top N
        5. Notify Teams

        Returns list of top-N lead dicts.
        """
        score_repo = ScoreRepository(session)
        lead_repo = LeadRepository(session)

        # Step 1: Get all recent scored leads (top prospects)
        scored_snapshots = score_repo.get_top_prospects(limit=200)

        if not scored_snapshots:
            self.log_action(
                "get_daily_top5",
                "No scored leads found",
                status="skipped",
            )
            return []

        # Deduplicate: keep only the latest score per lead
        seen_leads = set()
        unique_snapshots = []
        for snapshot in scored_snapshots:
            if snapshot.lead_id not in seen_leads:
                seen_leads.add(snapshot.lead_id)
                unique_snapshots.append(snapshot)

        # Step 2: Build scored lead dicts with full context
        scored_leads = []
        for snapshot in unique_snapshots:
            lead = lead_repo.get_by_id(snapshot.lead_id)
            if not lead:
                continue

            # Skip suppressed leads
            if snapshot.priority_tier == "suppressed":
                continue

            # Skip opted-out leads
            if lead.opt_out_flag:
                continue

            # Skip leads not in actionable statuses
            if lead.status in ("closed", "disqualified", "converted"):
                continue

            lead_dict = self._build_lead_dict(lead, snapshot, session)
            scored_leads.append(lead_dict)

        self.log_action(
            "get_daily_top5",
            f"Loaded {len(scored_leads)} scored, active leads",
        )

        # Step 3: Apply overrides
        filtered_leads = self.apply_overrides(scored_leads, session)

        # Step 4: Rank
        ranked = self.rank_leads(filtered_leads)

        # Step 5: Select top N
        top_n = self.select_top(ranked, n=n)

        # Step 6: Send to Teams
        self._send_teams_summary(top_n)

        self.log_action(
            "get_daily_top5",
            f"Selected top {len(top_n)} leads for daily outreach",
            metadata={"lead_ids": [l["lead_id"] for l in top_n]},
        )

        return top_n

    def rank_leads(
        self,
        scored_leads: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Rank leads by sales probability with tie-break logic.

        Uses tie_break_leads from the scoring skill which orders by:
          1. probability (desc)
          2. fit_score (desc)
          3. engagement_score (desc)
          4. margin_score (desc)
          5. on-site territory preferred
          6. newer leads preferred

        Returns sorted list (highest priority first).
        """
        ranked = tie_break_leads(scored_leads)
        self.log_action(
            "rank_leads",
            f"Ranked {len(ranked)} leads",
        )
        return ranked

    def apply_overrides(
        self,
        leads: List[Dict[str, Any]],
        session: Session,
    ) -> List[Dict[str, Any]]:
        """
        Apply override rules to the lead list.

        - Suppress opt-outs and invalid emails
        - Boost inbound quotes to top
        - Boost Tallman referrals
        - Boost Midwest manufacturing + Epicor combos

        Returns filtered and adjusted lead list.
        """
        suppression_repo = SuppressionRepository(session)
        result = []

        for lead_data in leads:
            email = lead_data.get("email", "")

            # Check suppression
            if email and suppression_repo.is_suppressed(email):
                self.log_action(
                    "apply_overrides",
                    f"Suppressed: {lead_data['lead_id'][:8]}… (email suppressed)",
                    status="skipped",
                )
                continue

            # Build override input
            override_input = {
                "opt_out": lead_data.get("opt_out", False),
                "email_valid": not (email and suppression_repo.is_suppressed(email)),
                "inbound_quote": lead_data.get("inbound_quote", False),
                "tallman_referral": lead_data.get("tallman_referral", False),
                "midwest": lead_data.get("geo_zone", "") == "midwest",
                "manufacturing": lead_data.get("manufacturing", False),
                "epicor": lead_data.get("epicor", False),
            }

            probability, package_fit, suppress_reason = apply_override_rules(
                override_input,
                lead_data.get("probability", 0),
                lead_data.get("package_fit_score", 0),
            )

            if suppress_reason:
                self.log_action(
                    "apply_overrides",
                    f"Suppressed: {lead_data['lead_id'][:8]}… ({suppress_reason})",
                    status="skipped",
                )
                continue

            # Update with adjusted scores
            lead_data["probability"] = probability
            lead_data["package_fit_score"] = package_fit
            lead_data["priority_tier"] = (
                "tier1" if probability >= 80 else
                "tier2" if probability >= 60 else
                "tier3" if probability >= 40 else
                "tier4"
            )
            result.append(lead_data)

        self.log_action(
            "apply_overrides",
            f"After overrides: {len(result)} leads remain (from {len(leads)})",
        )

        return result

    def select_top(
        self,
        ranked_leads: List[Dict[str, Any]],
        n: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Select the top N leads from the ranked list.

        Returns at most N leads.
        """
        top = ranked_leads[:n]
        self.log_action(
            "select_top",
            f"Selected top {len(top)} from {len(ranked_leads)} ranked leads",
        )
        return top

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_lead_dict(
        self,
        lead,
        snapshot,
        session: Session,
    ) -> Dict[str, Any]:
        """Build a comprehensive lead dict for ranking."""
        company_repo = CompanyRepository(session)
        contact_repo = ContactRepository(session)
        signal_repo = SignalRepository(session)

        company = company_repo.get_by_id(lead.company_id) if lead.company_id else None
        contact = contact_repo.get_by_id(lead.contact_id) if lead.contact_id else None
        signals = signal_repo.get_by_lead(lead.lead_id)

        state_code = _parse_state_code(company.geography if company else None)
        geo_zone = get_geo_zone(state_code)

        # Detect override-relevant flags
        source_name = ""
        if lead.source:
            source_name = (lead.source.source_name or "").lower()

        is_inbound = any(kw in source_name for kw in ["inbound", "quote", "request"])
        is_tallman = "tallman" in source_name
        is_manufacturing = False
        is_epicor = False

        if company and company.industry:
            is_manufacturing = "manufactur" in company.industry.lower()
        if signals:
            is_manufacturing = is_manufacturing or (signals.manufacturing_signal or 0) >= 0.3
            is_epicor = (signals.epicor_signal or 0) >= 0.5

        # Get service name for display
        offer_id = lead.recommended_offer or "technical_audit"
        offer_name = SERVICES[offer_id].name if offer_id in SERVICES else offer_id

        return {
            "lead_id": lead.lead_id,
            "company_name": company.company_name if company else "Unknown",
            "contact_name": contact.full_name if contact else "Unknown",
            "contact_title": contact.title if contact else "",
            "email": contact.email if contact else "",
            "industry": company.industry if company else "",
            "employee_band": company.employee_band if company else "",
            "geo_zone": geo_zone.value,
            "state_code": state_code,
            "on_site_territory": geo_zone.value in ("midwest", "north_florida"),
            "recommended_offer": offer_id,
            "recommended_offer_name": offer_name,
            "recommended_cta": lead.recommended_entry_cta or "",
            "probability": snapshot.sales_probability or 0.0,
            "fit_score": snapshot.fit_score or 0.0,
            "need_score": snapshot.need_score or 0.0,
            "engagement_score": snapshot.engagement_score or 0.0,
            "package_fit_score": snapshot.package_fit_score or 0.0,
            "margin_band": snapshot.margin_band or "",
            "margin_score": 0.0,  # Will be set during ranking
            "priority_tier": snapshot.priority_tier or "tier4",
            "recommended_action": snapshot.recommended_action or "",
            "status": lead.status,
            "opt_out": lead.opt_out_flag or False,
            "inbound_quote": is_inbound,
            "tallman_referral": is_tallman,
            "manufacturing": is_manufacturing,
            "epicor": is_epicor,
            "created_at": lead.created_at.isoformat() if lead.created_at else "",
            "scored_at": snapshot.scored_at.isoformat() if snapshot.scored_at else "",
        }

    def _send_teams_summary(self, top_leads: List[Dict[str, Any]]) -> bool:
        """
        Send the daily top-5 summary to Microsoft Teams.

        Returns True if the Teams message was sent successfully.
        """
        if not top_leads:
            self.log_action(
                "send_teams_summary",
                "No leads to send - skipping Teams notification",
                status="skipped",
            )
            return False

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        title = f"🎯 Daily Top {len(top_leads)} Leads — {today}"

        facts = []
        for i, lead in enumerate(top_leads, 1):
            company = lead.get("company_name", "Unknown")
            contact = lead.get("contact_name", "Unknown")
            prob = lead.get("probability", 0)
            tier = lead.get("priority_tier", "?")
            offer = lead.get("recommended_offer_name", "?")
            cta = lead.get("recommended_cta", "")

            facts.append({
                "title": f"#{i} — {company}",
                "value": (
                    f"{contact} | Prob: {prob:.0f}% | {tier} | "
                    f"Offer: {offer}"
                ),
            })

        # Add summary row
        total_prob = sum(l.get("probability", 0) for l in top_leads)
        avg_prob = total_prob / len(top_leads) if top_leads else 0
        facts.append({
            "title": "Average Probability",
            "value": f"{avg_prob:.1f}%",
        })

        success = send_teams_card(title=title, facts=facts)

        self.log_action(
            "send_teams_summary",
            f"Teams notification {'sent' if success else 'failed'} "
            f"for {len(top_leads)} leads",
            status="success" if success else "failure",
        )

        return success
