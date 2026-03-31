"""
MCRcore Growth Engine - Offer Matching Skill

Package routing matrix, audit-first rules, and geo-service eligibility
logic used by the OfferMatchingAgent. Pure functions with no DB dependency.
"""

from typing import Any, Dict, List, Optional, Tuple

from config.geo_routing import (
    GeoZone,
    ServiceEligibility,
    get_geo_zone,
    get_eligible_services,
    get_service_eligibility,
)
from config.service_catalog import SERVICES, SERVICE_CATALOG, MarginBand


# ---------------------------------------------------------------------------
# Package Routing Matrix
# ---------------------------------------------------------------------------
# Maps (signal_type, geo_zone) -> (primary_offer, secondary_offers)

PACKAGE_ROUTING_MATRIX: Dict[str, Dict[str, Tuple[str, List[str]]]] = {
    "erp_epicor": {
        GeoZone.MIDWEST.value: ("total_plan", ["virtual_servers", "fractional_cio"]),
        GeoZone.NORTH_FLORIDA.value: ("total_plan", ["virtual_servers", "fractional_cio"]),
        GeoZone.REMOTE_NA.value: ("virtual_servers", ["proactive_monitoring", "essential_cybersecurity"]),
    },
    "erp_mcleod": {
        GeoZone.MIDWEST.value: ("total_plan", ["virtual_servers", "proactive_monitoring"]),
        GeoZone.NORTH_FLORIDA.value: ("total_plan", ["virtual_servers", "proactive_monitoring"]),
        GeoZone.REMOTE_NA.value: ("virtual_servers", ["proactive_monitoring", "essential_cybersecurity"]),
    },
    "compliance": {
        GeoZone.MIDWEST.value: ("proactive_monitoring", ["essential_cybersecurity", "technical_audit"]),
        GeoZone.NORTH_FLORIDA.value: ("proactive_monitoring", ["essential_cybersecurity", "technical_audit"]),
        GeoZone.REMOTE_NA.value: ("proactive_monitoring", ["essential_cybersecurity"]),
    },
    "remote_workforce": {
        GeoZone.MIDWEST.value: ("wfh_implementation", ["virtual_servers", "essential_cybersecurity"]),
        GeoZone.NORTH_FLORIDA.value: ("wfh_implementation", ["virtual_servers", "essential_cybersecurity"]),
        GeoZone.REMOTE_NA.value: ("virtual_servers", ["wfh_implementation", "essential_cybersecurity"]),
    },
    "downtime_pain": {
        GeoZone.MIDWEST.value: ("total_plan", ["proactive_monitoring"]),
        GeoZone.NORTH_FLORIDA.value: ("total_plan", ["proactive_monitoring"]),
        GeoZone.REMOTE_NA.value: ("proactive_monitoring", ["essential_cybersecurity"]),
    },
    "scaling": {
        GeoZone.MIDWEST.value: ("total_plan", ["fractional_cio", "it_process_automation"]),
        GeoZone.NORTH_FLORIDA.value: ("total_plan", ["fractional_cio", "it_process_automation"]),
        GeoZone.REMOTE_NA.value: ("fractional_cio", ["proactive_monitoring", "essential_cybersecurity"]),
    },
    "no_it_team": {
        GeoZone.MIDWEST.value: ("total_plan", ["essential_cybersecurity"]),
        GeoZone.NORTH_FLORIDA.value: ("total_plan", ["essential_cybersecurity"]),
        GeoZone.REMOTE_NA.value: ("essential_cybersecurity", ["proactive_monitoring"]),
    },
}


# ---------------------------------------------------------------------------
# Size-based default offers
# ---------------------------------------------------------------------------

SIZE_DEFAULT_OFFERS = {
    "micro": ("essential_cybersecurity", ["proactive_monitoring", "technical_audit"]),
    "small": ("total_plan", ["essential_cybersecurity", "fractional_cio"]),
    "mid": ("total_plan", ["fractional_cio", "it_process_automation"]),
}


# ---------------------------------------------------------------------------
# Audit-First Rules
# ---------------------------------------------------------------------------

# Temperature thresholds for recommending audit-first CTA
# Lower temperature = colder outreach = stronger audit-first recommendation

AUDIT_FIRST_TEMPERATURE_THRESHOLD = 0.5  # Below this -> always audit first

AUDIT_FIRST_CTA_TEMPLATES = {
    "cold": "Free Technical Audit — see where your IT stands in 30 minutes",
    "warm": "Complimentary IT Assessment — identify your top 3 risks",
    "hot": "Schedule your technical deep-dive — we'll build your roadmap",
}

CTA_TEMPLATES = {
    "technical_audit": "Book a Free Technical Audit",
    "essential_cybersecurity": "Get a Cybersecurity Health Check",
    "total_plan": "See how Total Plan saves vs. in-house IT",
    "virtual_servers": "Get a Cloud Migration Assessment",
    "proactive_monitoring": "Request a Free Network Health Scan",
    "wfh_implementation": "Remote Work Readiness Assessment",
    "fractional_cio": "Book a Strategy Session with our vCIO",
    "on_demand_break_fix": "Request IT Support Now",
    "it_process_automation": "Automation ROI Assessment",
    "voip": "Get a Phone System Upgrade Quote",
}


# ---------------------------------------------------------------------------
# Expansion Paths
# ---------------------------------------------------------------------------

EXPANSION_PATHS: Dict[str, Dict[str, List[str]]] = {
    "essential_cybersecurity": {
        "micro": ["proactive_monitoring", "technical_audit"],
        "small": ["proactive_monitoring", "total_plan"],
        "mid": ["total_plan", "fractional_cio"],
    },
    "proactive_monitoring": {
        "micro": ["essential_cybersecurity", "total_plan"],
        "small": ["total_plan", "virtual_servers"],
        "mid": ["total_plan", "fractional_cio"],
    },
    "total_plan": {
        "micro": ["fractional_cio"],
        "small": ["fractional_cio", "it_process_automation"],
        "mid": ["fractional_cio", "it_process_automation", "virtual_servers"],
    },
    "virtual_servers": {
        "micro": ["proactive_monitoring", "essential_cybersecurity"],
        "small": ["total_plan", "proactive_monitoring"],
        "mid": ["total_plan", "it_process_automation"],
    },
    "technical_audit": {
        "micro": ["essential_cybersecurity", "proactive_monitoring"],
        "small": ["total_plan", "essential_cybersecurity"],
        "mid": ["total_plan", "fractional_cio"],
    },
    "wfh_implementation": {
        "micro": ["essential_cybersecurity", "voip"],
        "small": ["total_plan", "essential_cybersecurity"],
        "mid": ["total_plan", "virtual_servers"],
    },
    "on_demand_break_fix": {
        "micro": ["essential_cybersecurity", "proactive_monitoring"],
        "small": ["total_plan", "proactive_monitoring"],
        "mid": ["total_plan"],
    },
    "fractional_cio": {
        "micro": ["total_plan"],
        "small": ["total_plan", "it_process_automation"],
        "mid": ["it_process_automation", "total_plan"],
    },
    "it_process_automation": {
        "micro": ["total_plan"],
        "small": ["fractional_cio", "total_plan"],
        "mid": ["fractional_cio"],
    },
    "voip": {
        "micro": ["total_plan", "wfh_implementation"],
        "small": ["total_plan"],
        "mid": ["total_plan"],
    },
}


# ---------------------------------------------------------------------------
# Pure Skill Functions
# ---------------------------------------------------------------------------

def classify_lead_temperature(
    has_replied: bool = False,
    has_clicked: bool = False,
    has_opened: bool = False,
    inbound_request: bool = False,
    referral: bool = False,
) -> str:
    """
    Classify lead temperature as 'hot', 'warm', or 'cold'.

    Returns one of: 'hot', 'warm', 'cold'
    """
    if inbound_request or has_replied:
        return "hot"
    if referral or has_clicked:
        return "warm"
    if has_opened:
        return "warm"
    return "cold"


def detect_primary_signal(
    enrichment: Optional[Dict[str, Any]] = None,
    signals: Optional[Dict[str, float]] = None,
) -> str:
    """
    Determine the dominant signal type for routing.

    Returns one of the PACKAGE_ROUTING_MATRIX keys or 'none'.
    """
    enrichment = enrichment or {}
    signals = signals or {}

    # Check ERP signals first (highest routing impact)
    epicor_strength = signals.get("epicor_signal", 0.0)
    por_strength = signals.get("por_signal", 0.0)
    mcleod_strength = signals.get("mcleod_signal", 0.0)

    erp_text = (enrichment.get("erp_signals") or "").lower()
    if epicor_strength >= 0.5 or "epicor" in erp_text or "p21" in erp_text or "prophet" in erp_text:
        return "erp_epicor"
    if mcleod_strength >= 0.5 or "mcleod" in erp_text:
        return "erp_mcleod"

    # Compliance signals
    compliance_text = (enrichment.get("compliance_signals") or "").lower()
    if any(kw in compliance_text for kw in ["hipaa", "cmmc", "soc2", "pci", "nist", "compliance"]):
        return "compliance"

    # Remote workforce
    remote_text = (enrichment.get("remote_work_signals") or "").lower()
    if any(kw in remote_text for kw in ["remote", "hybrid", "wfh", "work from home"]):
        return "remote_workforce"

    # Scaling signal
    scaling_strength = signals.get("scaling_signal", 0.0)
    if scaling_strength >= 0.5:
        return "scaling"

    # IT pain / downtime
    it_pain = (enrichment.get("it_pain_points") or "").lower()
    if any(kw in it_pain for kw in ["downtime", "outage", "slow", "unreliable"]):
        return "downtime_pain"

    # No IT team / weak internal IT
    if any(kw in it_pain for kw in ["no it", "no dedicated", "one-person", "lone"]):
        return "no_it_team"

    return "none"


def resolve_offer_for_signal_and_geo(
    signal_type: str,
    geo_zone: GeoZone,
) -> Tuple[str, List[str]]:
    """
    Look up the package routing matrix for a signal type + geo zone.

    Returns (primary_service_id, [secondary_service_ids]).
    Falls back to technical_audit if no match.
    """
    zone_key = geo_zone.value
    routing = PACKAGE_ROUTING_MATRIX.get(signal_type, {})
    match = routing.get(zone_key)
    if match:
        return match
    return ("technical_audit", ["essential_cybersecurity"])


def resolve_offer_for_size(size_band: str) -> Tuple[str, List[str]]:
    """
    Get default offer based on company size band.

    Args:
        size_band: One of 'micro', 'small', 'mid'.

    Returns (primary_service_id, [secondary_service_ids]).
    """
    return SIZE_DEFAULT_OFFERS.get(
        size_band,
        ("essential_cybersecurity", ["technical_audit"]),
    )


def get_expansion_path(entry_offer: str, size_band: str) -> List[str]:
    """
    Get the expansion path from an entry offer given company size.

    Returns list of service IDs representing the recommended upsell path.
    """
    offer_paths = EXPANSION_PATHS.get(entry_offer, {})
    return offer_paths.get(size_band, ["total_plan"])


def get_cta_for_offer(
    offer_id: str,
    temperature: str = "cold",
) -> str:
    """
    Get the best CTA text for a given offer and temperature.

    Cold outreach ALWAYS gets audit-first CTA regardless of offer.
    """
    if temperature == "cold":
        return AUDIT_FIRST_CTA_TEMPLATES["cold"]
    if temperature == "warm":
        return CTA_TEMPLATES.get(offer_id, AUDIT_FIRST_CTA_TEMPLATES["warm"])
    # Hot leads get offer-specific CTA
    return CTA_TEMPLATES.get(offer_id, AUDIT_FIRST_CTA_TEMPLATES["hot"])


def filter_eligible_offers(
    offers: List[str],
    state_code: str = "",
    zip_code: str = "",
    country: str = "US",
) -> List[str]:
    """
    Filter a list of service IDs to only those eligible in the given geography.
    """
    eligible = get_eligible_services(state_code, zip_code, country)
    return [o for o in offers if o in eligible]


def is_on_site_territory(geo_zone: GeoZone) -> bool:
    """Check if a geo zone supports on-site services."""
    return geo_zone in (GeoZone.MIDWEST, GeoZone.NORTH_FLORIDA)
