"""
MCRcore Growth Engine - Offer Matching Agent

Maps each lead to the most relevant MCRcore service package.
Chooses entry offer, long-term expansion path, and recommends best CTA.
Strongly favors Technical Audit as initial CTA for colder outreach.

Uses geo routing: Midwest/N.Florida get Total Plan/ERP/on-site offers;
remote NA gets virtual servers/monitoring/cybersecurity.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.skills.offer_matching import (
    classify_lead_temperature,
    detect_primary_signal,
    filter_eligible_offers,
    get_cta_for_offer,
    get_expansion_path,
    is_on_site_territory,
    resolve_offer_for_signal_and_geo,
    resolve_offer_for_size,
    AUDIT_FIRST_CTA_TEMPLATES,
    CTA_TEMPLATES,
)
from config.geo_routing import (
    GeoZone,
    get_geo_zone,
    get_service_eligibility,
    ServiceEligibility,
)
from config.icp_rules import COMPANY_SIZE_BANDS, SizeBand
from config.service_catalog import SERVICES
from db.repositories import (
    CompanyRepository,
    ContactRepository,
    EnrichmentRepository,
    LeadRepository,
    SignalRepository,
)


def _employee_band_to_size_band(employee_band: Optional[str]) -> str:
    """Convert a company employee_band string like '50-200' into a size label."""
    if not employee_band:
        return "small"  # default
    # Parse the band string
    try:
        parts = employee_band.replace("+", "").split("-")
        low = int(parts[0].strip())
    except (ValueError, IndexError):
        return "small"
    if low < 25:
        return "micro"
    elif low < 50:
        return "small"
    else:
        return "mid"


def _employee_band_to_count(employee_band: Optional[str]) -> Optional[int]:
    """Extract an approximate employee count from band string."""
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


def _parse_geo_from_company(company) -> Tuple[str, str, str]:
    """Extract state_code, zip_code, country from company geography field."""
    geo = (company.geography or "") if company else ""
    state_code = ""
    zip_code = ""
    country = "US"

    # Try to parse geography - could be "IL", "FL 32207", "Chicago, IL", etc.
    geo_parts = geo.replace(",", " ").split()
    for part in geo_parts:
        cleaned = part.strip().upper()
        if len(cleaned) == 2 and cleaned.isalpha():
            state_code = cleaned
        elif cleaned.isdigit() and len(cleaned) == 5:
            zip_code = cleaned
        elif cleaned in ("US", "CA"):
            country = cleaned

    return state_code, zip_code, country


class OfferMatchingAgent(BaseAgent):
    """
    Agent that maps leads to MCRcore service packages.

    For each lead, determines:
      - Best entry offer based on enrichment, signals, and geography
      - Long-term expansion/upsell path
      - Best CTA (strongly favoring Technical Audit for cold outreach)

    Updates lead.recommended_offer and lead.recommended_entry_cta in the DB.
    """

    def __init__(self):
        super().__init__(
            name="OfferMatchingAgent",
            description="Maps leads to service packages, entry offers, and CTAs",
        )

    def run(self, lead_id: str, session: Session) -> Dict[str, Any]:
        """
        Primary entry point. Match offer for a single lead.

        Args:
            lead_id: UUID of the lead to match.
            session: SQLAlchemy session.

        Returns:
            Dict with matching results.
        """
        return self.match_offer(lead_id, session)

    def match_offer(self, lead_id: str, session: Session) -> Dict[str, Any]:
        """
        Full offer matching pipeline for a lead.

        Loads lead + company + enrichment + signals, determines geo zone,
        runs signal detection, selects entry offer, expansion path, and CTA.
        Updates the lead record in the database.
        """
        lead_repo = LeadRepository(session)
        company_repo = CompanyRepository(session)
        enrichment_repo = EnrichmentRepository(session)
        signal_repo = SignalRepository(session)

        lead = lead_repo.get_by_id(lead_id)
        if not lead:
            self.log_action("match_offer", f"Lead {lead_id} not found", status="failure")
            return {"error": f"Lead {lead_id} not found"}

        # Load related data
        company = company_repo.get_by_id(lead.company_id) if lead.company_id else None
        enrichment = enrichment_repo.get_by_lead(lead_id)
        signals = signal_repo.get_by_lead(lead_id)

        # Parse geography
        state_code, zip_code, country = _parse_geo_from_company(company)
        geo_zone = get_geo_zone(state_code, zip_code, country)

        # Build enrichment dict for skills
        enrichment_dict = {}
        if enrichment:
            enrichment_dict = {
                "erp_signals": enrichment.erp_signals,
                "compliance_signals": enrichment.compliance_signals,
                "remote_work_signals": enrichment.remote_work_signals,
                "it_pain_points": enrichment.it_pain_points,
                "infrastructure_signals": enrichment.infrastructure_signals,
                "operational_pain_summary": enrichment.operational_pain_summary,
            }

        # Build signals dict
        signals_dict = {}
        if signals:
            signals_dict = {
                "epicor_signal": signals.epicor_signal or 0.0,
                "por_signal": signals.por_signal or 0.0,
                "mcleod_signal": signals.mcleod_signal or 0.0,
                "dat_keypoint_signal": signals.dat_keypoint_signal or 0.0,
                "manufacturing_signal": signals.manufacturing_signal or 0.0,
                "logistics_signal": signals.logistics_signal or 0.0,
                "insurance_signal": signals.insurance_signal or 0.0,
                "scaling_signal": signals.scaling_signal or 0.0,
            }

        # Determine company size
        size_band = _employee_band_to_size_band(
            company.employee_band if company else None
        )
        employee_count = _employee_band_to_count(
            company.employee_band if company else None
        )

        # Step 1: Determine entry offer
        entry_offer, secondary_offers = self.determine_entry_offer(
            enrichment_dict, signals_dict, geo_zone, size_band,
        )

        # Filter for geo eligibility
        all_offers = [entry_offer] + secondary_offers
        eligible = filter_eligible_offers(all_offers, state_code, zip_code, country)
        if eligible and entry_offer not in eligible:
            entry_offer = eligible[0]
        elif not eligible:
            # Fallback: technical audit is always available
            entry_offer = "technical_audit"

        # Step 2: Determine expansion path
        expansion_path = self.determine_expansion_path(entry_offer, size_band)

        # Step 3: Determine lead temperature and CTA
        temperature = self._assess_temperature(lead)
        cta = self.recommend_cta(temperature, entry_offer)

        # Step 4: Get audit-first recommendation
        audit_rec = self.get_audit_first_recommendation({
            "temperature": temperature,
            "geo_zone": geo_zone.value,
            "size_band": size_band,
            "entry_offer": entry_offer,
        })

        # Build result
        service_name = SERVICES.get(entry_offer, None)
        result = {
            "lead_id": lead_id,
            "entry_offer": entry_offer,
            "entry_offer_name": service_name.name if service_name else entry_offer,
            "secondary_offers": secondary_offers,
            "expansion_path": expansion_path,
            "cta": cta,
            "audit_first_recommendation": audit_rec,
            "geo_zone": geo_zone.value,
            "size_band": size_band,
            "temperature": temperature,
            "primary_signal": detect_primary_signal(enrichment_dict, signals_dict),
        }

        # Step 5: Update lead record
        lead_repo.update(
            lead_id,
            recommended_offer=entry_offer,
            recommended_entry_cta=cta,
            last_processed_at=datetime.now(timezone.utc),
        )
        session.commit()

        self.log_action(
            "match_offer",
            f"Lead {lead_id[:8]}… -> {entry_offer} (CTA: {cta[:50]}…)",
            metadata=result,
        )

        return result

    def determine_entry_offer(
        self,
        enrichment: Dict[str, Any],
        signals: Dict[str, float],
        geo_zone: GeoZone,
        size_band: str = "small",
    ) -> Tuple[str, List[str]]:
        """
        Determine the best entry offer based on enrichment, signals, and geo.

        Decision priority:
          1. Signal-based routing (ERP, compliance, remote, etc.)
          2. Size-based default if no strong signals
          3. Geo-filtered eligibility

        Returns (primary_offer_id, [secondary_offer_ids]).
        """
        # Detect primary signal
        signal_type = detect_primary_signal(enrichment, signals)

        if signal_type != "none":
            # Route by signal + geo
            primary, secondaries = resolve_offer_for_signal_and_geo(
                signal_type, geo_zone,
            )
            self.log_action(
                "determine_entry_offer",
                f"Signal-based: {signal_type} + {geo_zone.value} -> {primary}",
            )
            return primary, secondaries

        # No strong signal -> size-based default
        primary, secondaries = resolve_offer_for_size(size_band)
        self.log_action(
            "determine_entry_offer",
            f"Size-based: {size_band} -> {primary}",
        )
        return primary, secondaries

    def determine_expansion_path(
        self,
        entry_offer: str,
        company_size: str,
    ) -> List[str]:
        """
        Determine the long-term expansion/upsell path from an entry offer.

        Args:
            entry_offer: The initial service offering ID.
            company_size: One of 'micro', 'small', 'mid'.

        Returns:
            Ordered list of service IDs for the expansion path.
        """
        path = get_expansion_path(entry_offer, company_size)
        self.log_action(
            "determine_expansion_path",
            f"{entry_offer} ({company_size}) -> {' -> '.join(path)}",
        )
        return path

    def recommend_cta(
        self,
        lead_temperature: str,
        offer: str,
    ) -> str:
        """
        Recommend the best CTA for a lead.

        STRONGLY favors Technical Audit as initial CTA for colder outreach.

        Args:
            lead_temperature: 'hot', 'warm', or 'cold'.
            offer: The matched service offering ID.

        Returns:
            CTA string.
        """
        cta = get_cta_for_offer(offer, lead_temperature)
        self.log_action(
            "recommend_cta",
            f"temp={lead_temperature}, offer={offer} -> CTA: {cta}",
        )
        return cta

    def get_audit_first_recommendation(
        self,
        lead_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate audit-first recommendation details.

        For cold outreach, the Technical Audit is ALWAYS the recommended
        initial engagement, regardless of the matched package. The matched
        package becomes the post-audit recommendation.

        Args:
            lead_data: Dict with temperature, geo_zone, size_band, entry_offer.

        Returns:
            Dict with audit recommendation details.
        """
        temperature = lead_data.get("temperature", "cold")
        entry_offer = lead_data.get("entry_offer", "technical_audit")
        geo_zone = lead_data.get("geo_zone", "remote_north_america")

        recommend_audit_first = temperature in ("cold", "warm")

        if recommend_audit_first:
            audit_cta = AUDIT_FIRST_CTA_TEMPLATES.get(temperature, AUDIT_FIRST_CTA_TEMPLATES["cold"])
            return {
                "recommend_audit_first": True,
                "audit_cta": audit_cta,
                "post_audit_offer": entry_offer,
                "post_audit_offer_name": SERVICES.get(entry_offer, {entry_offer}).name
                    if entry_offer in SERVICES else entry_offer,
                "rationale": (
                    f"Temperature is '{temperature}' - lead Technical Audit to build trust, "
                    f"then transition to {entry_offer} recommendation post-audit."
                ),
            }
        else:
            return {
                "recommend_audit_first": False,
                "audit_cta": None,
                "post_audit_offer": entry_offer,
                "post_audit_offer_name": SERVICES.get(entry_offer, {entry_offer}).name
                    if entry_offer in SERVICES else entry_offer,
                "rationale": (
                    f"Temperature is '{temperature}' - lead is warm enough for direct "
                    f"{entry_offer} pitch."
                ),
            }

    def _assess_temperature(self, lead) -> str:
        """
        Determine lead temperature from the lead record and related events.

        A simplified assessment based on available lead-level data.
        For full engagement-based temperature, use the scoring agent.
        """
        # Check source for inbound/referral signals
        source_name = ""
        if lead.source:
            source_name = (lead.source.source_name or "").lower()

        inbound = "inbound" in source_name or "quote" in source_name
        referral = "referral" in source_name or "tallman" in source_name

        # Check if lead has any reply events indicating warmth
        has_replied = False
        has_opened = False
        has_clicked = False
        try:
            reply_count = lead.reply_events.count()
            has_replied = reply_count > 0
        except Exception:
            pass
        try:
            outreach = lead.outreach_events.all()
            for event in outreach:
                if event.open_status:
                    has_opened = True
                if event.click_status:
                    has_clicked = True
        except Exception:
            pass

        return classify_lead_temperature(
            has_replied=has_replied,
            has_clicked=has_clicked,
            has_opened=has_opened,
            inbound_request=inbound,
            referral=referral,
        )
