"""
MCRcore Growth Engine - Scoring Agent

Calculates fit_score, need_score, engagement_score, package_fit_score,
margin_band, sales_probability, and priority_tier for each lead.

Weighted model: Fit 30%, Need 25%, Package fit 20%, Engagement 15%, Margin 10%.
Stores ScoreSnapshot via the repository layer.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.skills.lead_scoring import (
    ENGAGEMENT_WEIGHTS,
    FIT_WEIGHTS,
    NEED_WEIGHTS,
    OVERALL_WEIGHTS,
    SERVICE_MARGIN_MAP,
    apply_override_rules,
    assign_priority_tier,
    calculate_overall_probability,
    calculate_weighted_score,
    get_margin_band_for_service,
    get_margin_score,
    score_employee_size_fit,
    score_erp_evidence,
    score_geo_fit,
    score_industry_fit,
    score_managed_service_suitability,
    score_title_fit,
)
from config.geo_routing import get_geo_zone, GeoZone, MIDWEST_STATE_CODES
from config.icp_rules import TARGET_INDUSTRIES, TITLE_PRIORITY_MAP
from config.service_catalog import SERVICES
from db.repositories import (
    CompanyRepository,
    ContactRepository,
    EnrichmentRepository,
    LeadRepository,
    OutreachRepository,
    ReplyRepository,
    ScoreRepository,
    SignalRepository,
    SuppressionRepository,
)


def _parse_employee_count(employee_band: Optional[str]) -> Optional[int]:
    """Parse approximate employee count from band string like '50-200'."""
    if not employee_band:
        return None
    try:
        parts = employee_band.replace("+", "").split("-")
        low = int(parts[0].strip())
        if len(parts) > 1:
            high = int(parts[1].strip())
            return (low + high) // 2
        return low
    except (ValueError, IndexError):
        return None


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


class ScoringAgent(BaseAgent):
    """
    Agent that calculates comprehensive lead scores.

    Produces:
      - fit_score (company fit to ICP)
      - need_score (IT pain / need intensity)
      - engagement_score (behavioral signals)
      - package_fit_score (match quality to recommended offer)
      - margin_band (revenue potential tier)
      - sales_probability (weighted composite)
      - priority_tier (tier1-tier4)

    Applies override rules and stores ScoreSnapshot in the database.
    """

    def __init__(self):
        super().__init__(
            name="ScoringAgent",
            description="Calculates multi-dimensional lead scores and priority tiers",
        )

    def run(self, lead_id: str, session: Session) -> Dict[str, Any]:
        """Primary entry point. Score a single lead."""
        return self.score_lead(lead_id, session)

    def score_lead(self, lead_id: str, session: Session) -> Dict[str, Any]:
        """
        Full scoring pipeline for a lead.

        Loads all related data, calculates sub-scores, applies overrides,
        computes probability, assigns tier, and stores ScoreSnapshot.
        """
        lead_repo = LeadRepository(session)
        company_repo = CompanyRepository(session)
        contact_repo = ContactRepository(session)
        enrichment_repo = EnrichmentRepository(session)
        signal_repo = SignalRepository(session)
        outreach_repo = OutreachRepository(session)
        reply_repo = ReplyRepository(session)
        score_repo = ScoreRepository(session)
        suppression_repo = SuppressionRepository(session)

        lead = lead_repo.get_by_id(lead_id)
        if not lead:
            self.log_action("score_lead", f"Lead {lead_id} not found", status="failure")
            return {"error": f"Lead {lead_id} not found"}

        # Load related entities
        company = company_repo.get_by_id(lead.company_id) if lead.company_id else None
        contact = contact_repo.get_by_id(lead.contact_id) if lead.contact_id else None
        enrichment = enrichment_repo.get_by_lead(lead_id)
        signals = signal_repo.get_by_lead(lead_id)
        outreach_events = outreach_repo.get_by_lead(lead_id)
        reply_events = reply_repo.get_by_lead(lead_id)

        # Build data dicts for scoring functions
        enrichment_dict = self._enrichment_to_dict(enrichment)
        signals_dict = self._signals_to_dict(signals)

        # -- Calculate sub-scores --
        fit_score = self.calculate_fit(lead, company, contact, signals_dict)
        need_score = self.calculate_need(enrichment_dict, signals_dict)
        engagement_score = self.calculate_engagement(outreach_events, reply_events)

        # Package fit requires the recommended offer
        offer = lead.recommended_offer or "technical_audit"
        package_fit_score = self.calculate_package_fit(offer, signals_dict)

        # Margin band
        margin_band = self.estimate_margin_band(offer)
        margin_score = get_margin_score(margin_band)

        # -- Calculate probability --
        probability = self.calculate_probability({
            "fit": fit_score,
            "need": need_score,
            "engagement": engagement_score,
            "package_fit": package_fit_score,
            "margin": margin_score,
        })

        # -- Apply override rules --
        state_code = _parse_state_code(company.geography if company else None)
        email = contact.email if contact else None
        email_valid = True
        if email:
            email_valid = not suppression_repo.is_suppressed(email)

        override_data = {
            "opt_out": lead.opt_out_flag or False,
            "email_valid": email_valid,
            "inbound_quote": self._is_inbound_quote(lead),
            "tallman_referral": self._is_tallman_referral(lead),
            "midwest": state_code in MIDWEST_STATE_CODES,
            "manufacturing": self._has_manufacturing_signal(company, signals_dict),
            "epicor": signals_dict.get("epicor_signal", 0) >= 0.5,
        }

        probability, package_fit_score, suppress_reason = apply_override_rules(
            override_data, probability, package_fit_score,
        )

        # -- Assign tier --
        tier = self.assign_tier(probability)

        # Handle suppression
        if suppress_reason:
            tier = "suppressed"
            recommended_action = f"Suppressed: {suppress_reason}"
        else:
            recommended_action = self._recommend_action(tier, offer)

        # -- Store ScoreSnapshot --
        score_snapshot = score_repo.create(
            lead_id=lead_id,
            fit_score=round(fit_score, 2),
            need_score=round(need_score, 2),
            engagement_score=round(engagement_score, 2),
            package_fit_score=round(package_fit_score, 2),
            margin_band=margin_band,
            sales_probability=round(probability, 2),
            priority_tier=tier,
            recommended_action=recommended_action,
        )
        session.commit()

        result = {
            "lead_id": lead_id,
            "fit_score": round(fit_score, 2),
            "need_score": round(need_score, 2),
            "engagement_score": round(engagement_score, 2),
            "package_fit_score": round(package_fit_score, 2),
            "margin_band": margin_band,
            "margin_score": round(margin_score, 2),
            "sales_probability": round(probability, 2),
            "priority_tier": tier,
            "recommended_action": recommended_action,
            "suppress_reason": suppress_reason,
            "score_id": score_snapshot.score_id,
        }

        self.log_action(
            "score_lead",
            f"Lead {lead_id[:8]}… -> prob={probability:.1f} tier={tier}",
            metadata=result,
        )

        return result

    def calculate_fit(
        self,
        lead,
        company,
        contact,
        signals: Dict[str, float],
    ) -> float:
        """
        Calculate fit score (0-100).

        Components: employee_size_fit, industry_fit, geo_fit, title_fit,
        erp_evidence, managed_service_suitability.
        """
        employee_count = _parse_employee_count(
            company.employee_band if company else None
        )
        state_code = _parse_state_code(company.geography if company else None)
        geo_zone = get_geo_zone(state_code)

        # Detect whether company likely has IT staff
        has_it_staff = False
        if contact and contact.title:
            title_lower = contact.title.lower()
            has_it_staff = any(kw in title_lower for kw in [
                "it manager", "sys admin", "system admin", "network admin",
                "it director", "head of it",
            ])

        components = {
            "employee_size_fit": score_employee_size_fit(employee_count),
            "industry_fit": score_industry_fit(
                company.industry if company else None,
                TARGET_INDUSTRIES,
            ),
            "geo_fit": score_geo_fit(geo_zone.value),
            "title_fit": score_title_fit(
                contact.title if contact else None,
                TITLE_PRIORITY_MAP,
            ),
            "erp_evidence": score_erp_evidence(
                erp_signals_text=None,  # from enrichment, loaded separately
                epicor_signal=signals.get("epicor_signal", 0.0),
                mcleod_signal=signals.get("mcleod_signal", 0.0),
            ),
            "managed_service_suitability": score_managed_service_suitability(
                employee_count, has_it_staff,
            ),
        }

        return calculate_weighted_score(components, FIT_WEIGHTS)

    def calculate_need(
        self,
        enrichment: Dict[str, Any],
        signals: Dict[str, float],
    ) -> float:
        """
        Calculate need score (0-100).

        Components: support_complexity, compliance_burden, remote_hybrid_need,
        uptime_sensitivity, growth_strain, weak_internal_it.
        """
        components = {
            "support_complexity": self._score_support_complexity(enrichment, signals),
            "compliance_burden": self._score_compliance_burden(enrichment),
            "remote_hybrid_need": self._score_remote_need(enrichment),
            "uptime_sensitivity": self._score_uptime_sensitivity(enrichment, signals),
            "growth_strain": self._score_growth_strain(enrichment, signals),
            "weak_internal_it": self._score_weak_it(enrichment),
        }

        return calculate_weighted_score(components, NEED_WEIGHTS)

    def calculate_engagement(
        self,
        outreach_events: List,
        reply_events: List,
    ) -> float:
        """
        Calculate engagement score (0-100).

        Components: open, click, reply, positive_language, price_request,
        audit_request, stakeholder_referral.
        """
        has_open = False
        has_click = False
        for event in (outreach_events or []):
            if event.open_status:
                has_open = True
            if event.click_status:
                has_click = True

        has_reply = len(reply_events or []) > 0
        has_positive = False
        has_price_request = False
        has_audit_request = False
        has_stakeholder_referral = False

        for reply in (reply_events or []):
            classified = (reply.classified_as or "").lower()
            raw = (reply.raw_text or "").lower()

            if classified == "positive":
                has_positive = True
            if any(kw in raw for kw in ["price", "cost", "quote", "pricing", "how much"]):
                has_price_request = True
            if any(kw in raw for kw in ["audit", "assessment", "review"]):
                has_audit_request = True
            if any(kw in raw for kw in ["let me connect you", "talk to my", "cc'ing", "loop in"]):
                has_stakeholder_referral = True

        components = {
            "open": 100.0 if has_open else 0.0,
            "click": 100.0 if has_click else 0.0,
            "reply": 100.0 if has_reply else 0.0,
            "positive_language": 100.0 if has_positive else 0.0,
            "price_request": 100.0 if has_price_request else 0.0,
            "audit_request": 100.0 if has_audit_request else 0.0,
            "stakeholder_referral": 100.0 if has_stakeholder_referral else 0.0,
        }

        return calculate_weighted_score(components, ENGAGEMENT_WEIGHTS)

    def calculate_package_fit(
        self,
        offer: str,
        signals: Dict[str, float],
    ) -> float:
        """
        Calculate package fit score (0-100).

        How well the recommended offer matches the detected signals.
        """
        if not offer or offer not in SERVICES:
            return 30.0  # Unknown offer

        service = SERVICES[offer]
        score = 50.0  # Base score for any valid service match

        # Boost for signal alignment with service keywords
        signal_keywords = {
            "epicor_signal": ["epicor", "p21", "erp"],
            "mcleod_signal": ["mcleod", "freight", "logistics"],
            "manufacturing_signal": ["manufacturing", "industrial"],
            "logistics_signal": ["logistics", "supply chain"],
            "insurance_signal": ["insurance", "compliance"],
            "scaling_signal": ["scaling", "growing"],
        }

        for signal_key, keywords in signal_keywords.items():
            signal_strength = signals.get(signal_key, 0.0)
            if signal_strength >= 0.5:
                # Check if any of the signal's keywords match service keywords
                if any(kw in " ".join(service.keywords).lower() for kw in keywords):
                    score += 20.0 * signal_strength

        # Boost for recurring revenue services
        if service.recurring:
            score += 10.0

        # Boost for services in ideal size bands (general boost)
        if "small" in service.ideal_size_bands or "mid" in service.ideal_size_bands:
            score += 5.0

        return min(100.0, score)

    def estimate_margin_band(self, offer: str) -> str:
        """
        Estimate the margin band for a recommended offer.

        Returns one of: 'high', 'medium', 'low-wedge', 'tentative', 'variable'.
        """
        return get_margin_band_for_service(offer)

    def calculate_probability(self, scores: Dict[str, float]) -> float:
        """
        Calculate overall sales probability from sub-scores.

        Uses the weighted model: Fit 30%, Need 25%, Package 20%, 
        Engagement 15%, Margin 10%.
        """
        return calculate_overall_probability(
            fit_score=scores.get("fit", 0),
            need_score=scores.get("need", 0),
            engagement_score=scores.get("engagement", 0),
            package_fit_score=scores.get("package_fit", 0),
            margin_score=scores.get("margin", 0),
        )

    def assign_tier(self, probability: float) -> str:
        """
        Assign priority tier based on probability score.

        tier1: >=80, tier2: 60-79, tier3: 40-59, tier4: <40
        """
        return assign_priority_tier(probability)

    # ------------------------------------------------------------------
    # Private helper methods for need-score components
    # ------------------------------------------------------------------

    def _score_support_complexity(
        self,
        enrichment: Dict[str, Any],
        signals: Dict[str, float],
    ) -> float:
        """Score how complex the company's IT support needs are."""
        score = 30.0  # baseline
        it_pain = (enrichment.get("it_pain_points") or "").lower()
        infra = (enrichment.get("infrastructure_signals") or "").lower()

        complexity_keywords = [
            "multi-site", "multiple locations", "complex", "legacy",
            "integration", "erp", "custom", "24/7",
        ]
        for kw in complexity_keywords:
            if kw in it_pain or kw in infra:
                score += 12.0

        # ERP signals add complexity
        if signals.get("epicor_signal", 0) >= 0.3:
            score += 15.0
        if signals.get("mcleod_signal", 0) >= 0.3:
            score += 15.0

        return min(100.0, score)

    def _score_compliance_burden(self, enrichment: Dict[str, Any]) -> float:
        """Score the compliance burden/need intensity."""
        score = 10.0
        compliance_text = (enrichment.get("compliance_signals") or "").lower()
        compliance_keywords = [
            "hipaa", "cmmc", "soc2", "soc 2", "pci", "nist",
            "compliance", "regulated", "audit", "itar",
        ]
        for kw in compliance_keywords:
            if kw in compliance_text:
                score += 15.0
        return min(100.0, score)

    def _score_remote_need(self, enrichment: Dict[str, Any]) -> float:
        """Score remote/hybrid work need."""
        score = 10.0
        remote_text = (enrichment.get("remote_work_signals") or "").lower()
        remote_keywords = [
            "remote", "hybrid", "work from home", "wfh",
            "distributed", "virtual office",
        ]
        for kw in remote_keywords:
            if kw in remote_text:
                score += 20.0
        return min(100.0, score)

    def _score_uptime_sensitivity(
        self,
        enrichment: Dict[str, Any],
        signals: Dict[str, float],
    ) -> float:
        """Score how sensitive the business is to IT uptime."""
        score = 20.0
        it_pain = (enrichment.get("it_pain_points") or "").lower()
        uptime_keywords = [
            "downtime", "outage", "availability", "uptime",
            "mission critical", "24/7", "always on",
        ]
        for kw in uptime_keywords:
            if kw in it_pain:
                score += 15.0

        # Manufacturing and logistics are inherently uptime-sensitive
        if signals.get("manufacturing_signal", 0) >= 0.3:
            score += 20.0
        if signals.get("logistics_signal", 0) >= 0.3:
            score += 15.0

        return min(100.0, score)

    def _score_growth_strain(
        self,
        enrichment: Dict[str, Any],
        signals: Dict[str, float],
    ) -> float:
        """Score indicators of growth straining current IT."""
        score = 10.0
        pain = (enrichment.get("operational_pain_summary") or "").lower()
        growth_keywords = [
            "growing", "scaling", "expansion", "new office",
            "hiring", "acquisition", "merger",
        ]
        for kw in growth_keywords:
            if kw in pain:
                score += 15.0

        if signals.get("scaling_signal", 0) >= 0.3:
            score += 25.0

        return min(100.0, score)

    def _score_weak_it(self, enrichment: Dict[str, Any]) -> float:
        """Score indicators of weak/absent internal IT capability."""
        score = 10.0
        it_pain = (enrichment.get("it_pain_points") or "").lower()
        pain = (enrichment.get("operational_pain_summary") or "").lower()
        combined = it_pain + " " + pain

        weak_it_keywords = [
            "no it", "no dedicated", "one-person", "lone it",
            "part-time it", "owner handles", "ad hoc", "no support",
            "outsourced", "need help",
        ]
        for kw in weak_it_keywords:
            if kw in combined:
                score += 18.0

        return min(100.0, score)

    # ------------------------------------------------------------------
    # Private helpers for override detection
    # ------------------------------------------------------------------

    def _is_inbound_quote(self, lead) -> bool:
        """Check if lead originated from an inbound quote request."""
        if lead.source:
            name = (lead.source.source_name or "").lower()
            return any(kw in name for kw in ["inbound", "quote", "request", "form"])
        return False

    def _is_tallman_referral(self, lead) -> bool:
        """Check if lead was referred by Tallman."""
        if lead.source:
            name = (lead.source.source_name or "").lower()
            return "tallman" in name
        substatus = (lead.substatus or "").lower()
        return "tallman" in substatus

    def _has_manufacturing_signal(
        self,
        company,
        signals: Dict[str, float],
    ) -> bool:
        """Check if there's a manufacturing signal."""
        if signals.get("manufacturing_signal", 0) >= 0.3:
            return True
        if company and company.industry:
            return "manufactur" in company.industry.lower()
        return False

    def _recommend_action(self, tier: str, offer: str) -> str:
        """Generate recommended action string based on tier."""
        actions = {
            "tier1": f"Immediate outreach - pitch {offer} with urgency",
            "tier2": f"Prioritized sequence - lead with Technical Audit, transition to {offer}",
            "tier3": f"Nurture sequence - educational content, soft {offer} mention",
            "tier4": f"Monitor and nurture - long-term drip, revisit in 30 days",
        }
        return actions.get(tier, "Review manually")

    # ------------------------------------------------------------------
    # Data extraction helpers
    # ------------------------------------------------------------------

    def _enrichment_to_dict(self, enrichment) -> Dict[str, Any]:
        """Convert EnrichmentProfile ORM object to dict."""
        if not enrichment:
            return {}
        return {
            "operational_pain_summary": enrichment.operational_pain_summary,
            "it_pain_points": enrichment.it_pain_points,
            "erp_signals": enrichment.erp_signals,
            "compliance_signals": enrichment.compliance_signals,
            "remote_work_signals": enrichment.remote_work_signals,
            "infrastructure_signals": enrichment.infrastructure_signals,
            "evidence_json": enrichment.evidence_json,
            "research_confidence": enrichment.research_confidence,
            "company_summary": enrichment.company_summary,
        }

    def _signals_to_dict(self, signals) -> Dict[str, float]:
        """Convert SignalProfile ORM object to dict."""
        if not signals:
            return {}
        return {
            "epicor_signal": signals.epicor_signal or 0.0,
            "por_signal": signals.por_signal or 0.0,
            "mcleod_signal": signals.mcleod_signal or 0.0,
            "dat_keypoint_signal": signals.dat_keypoint_signal or 0.0,
            "manufacturing_signal": signals.manufacturing_signal or 0.0,
            "logistics_signal": signals.logistics_signal or 0.0,
            "insurance_signal": signals.insurance_signal or 0.0,
            "scaling_signal": signals.scaling_signal or 0.0,
        }
