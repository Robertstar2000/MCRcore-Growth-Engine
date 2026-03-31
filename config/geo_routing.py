"""
MCRcore Growth Engine - Geographic Routing Rules
Defines service territories, state/zip mappings, and service eligibility
by geography for the dual delivery model.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class GeoZone(Enum):
    MIDWEST = "midwest"
    NORTH_FLORIDA = "north_florida"
    REMOTE_NA = "remote_north_america"


class ServiceEligibility(Enum):
    ON_SITE = "on_site"         # Full on-site + remote support
    REMOTE_ONLY = "remote_only" # Remote support only
    NOT_AVAILABLE = "not_available"


# ---------------------------------------------------------------------------
# Midwest States (Primary on-site territory)
# ---------------------------------------------------------------------------

MIDWEST_STATES = {
    "IL": {"name": "Illinois", "primary": True, "metro_focus": ["Chicago", "Rockford", "Peoria"]},
    "IN": {"name": "Indiana", "primary": True, "metro_focus": ["Indianapolis", "Fort Wayne"]},
    "WI": {"name": "Wisconsin", "primary": True, "metro_focus": ["Milwaukee", "Madison"]},
    "MI": {"name": "Michigan", "primary": False, "metro_focus": ["Detroit", "Grand Rapids"]},
    "OH": {"name": "Ohio", "primary": False, "metro_focus": ["Columbus", "Cleveland", "Cincinnati"]},
    "IA": {"name": "Iowa", "primary": False, "metro_focus": ["Des Moines", "Cedar Rapids"]},
    "MN": {"name": "Minnesota", "primary": False, "metro_focus": ["Minneapolis", "St. Paul"]},
    "MO": {"name": "Missouri", "primary": False, "metro_focus": ["St. Louis", "Kansas City"]},
    "KS": {"name": "Kansas", "primary": False, "metro_focus": ["Kansas City", "Wichita"]},
    "NE": {"name": "Nebraska", "primary": False, "metro_focus": ["Omaha", "Lincoln"]},
    "SD": {"name": "South Dakota", "primary": False, "metro_focus": ["Sioux Falls"]},
    "ND": {"name": "North Dakota", "primary": False, "metro_focus": ["Fargo"]},
}

MIDWEST_STATE_CODES = list(MIDWEST_STATES.keys())


# ---------------------------------------------------------------------------
# Northern Florida (Secondary on-site territory)
# ---------------------------------------------------------------------------

NORTH_FLORIDA_ZIP_PREFIXES = [
    "320",  # Jacksonville area
    "321",  # East Central Florida (brevard overlap - include for routing)
    "322",  # Jacksonville / Duval County
    "323",  # Tallahassee area
    "324",  # Panama City area
    "325",  # Pensacola area
    "326",  # Gainesville area
    "327",  # Mid-Florida (Orlando/Daytona overlap - include selectively)
    "329",  # Melbourne / Brevard (northern Brevard)
    "344",  # Gainesville
]

NORTH_FLORIDA_METROS = [
    "Jacksonville", "Tallahassee", "Gainesville", "Pensacola",
    "Panama City", "Daytona Beach", "Ocala", "St. Augustine",
]


# ---------------------------------------------------------------------------
# North America (Full remote territory)
# ---------------------------------------------------------------------------

NORTH_AMERICA_COUNTRIES = ["US", "CA"]  # United States + Canada

# US states NOT in Midwest but eligible for remote services
ALL_US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
]

CANADIAN_PROVINCES = [
    "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT",
]


# ---------------------------------------------------------------------------
# Service Eligibility by Geography
# ---------------------------------------------------------------------------

SERVICE_GEO_ELIGIBILITY = {
    # --- Full-service (on-site + remote) in core territories ---
    "total_plan": {
        GeoZone.MIDWEST: ServiceEligibility.ON_SITE,
        GeoZone.NORTH_FLORIDA: ServiceEligibility.ON_SITE,
        GeoZone.REMOTE_NA: ServiceEligibility.NOT_AVAILABLE,
        "notes": "Total Plan requires on-site capability. Midwest + N.Florida only.",
    },
    "on_demand_break_fix": {
        GeoZone.MIDWEST: ServiceEligibility.ON_SITE,
        GeoZone.NORTH_FLORIDA: ServiceEligibility.ON_SITE,
        GeoZone.REMOTE_NA: ServiceEligibility.NOT_AVAILABLE,
        "notes": "Break/fix is inherently on-site. Core territories only.",
    },
    "technical_audit": {
        GeoZone.MIDWEST: ServiceEligibility.ON_SITE,
        GeoZone.NORTH_FLORIDA: ServiceEligibility.ON_SITE,
        GeoZone.REMOTE_NA: ServiceEligibility.REMOTE_ONLY,
        "notes": "Full audit on-site in core markets. Remote audit available for all NA.",
    },

    # --- ERP-specific (on-site preferred, remote possible) ---
    "virtual_servers": {
        GeoZone.MIDWEST: ServiceEligibility.ON_SITE,
        GeoZone.NORTH_FLORIDA: ServiceEligibility.ON_SITE,
        GeoZone.REMOTE_NA: ServiceEligibility.REMOTE_ONLY,
        "notes": "Server hosting is remote by nature. On-site for migration support.",
    },

    # --- Remote services available across all of North America ---
    "essential_cybersecurity": {
        GeoZone.MIDWEST: ServiceEligibility.ON_SITE,
        GeoZone.NORTH_FLORIDA: ServiceEligibility.ON_SITE,
        GeoZone.REMOTE_NA: ServiceEligibility.REMOTE_ONLY,
        "notes": "Cybersecurity stack is fully remote-deployable.",
    },
    "proactive_monitoring": {
        GeoZone.MIDWEST: ServiceEligibility.ON_SITE,
        GeoZone.NORTH_FLORIDA: ServiceEligibility.ON_SITE,
        GeoZone.REMOTE_NA: ServiceEligibility.REMOTE_ONLY,
        "notes": "Monitoring is remote. On-site for hardware sensor deployment.",
    },
    "fractional_cio": {
        GeoZone.MIDWEST: ServiceEligibility.ON_SITE,
        GeoZone.NORTH_FLORIDA: ServiceEligibility.ON_SITE,
        GeoZone.REMOTE_NA: ServiceEligibility.REMOTE_ONLY,
        "notes": "vCIO can operate fully remotely. On-site QBRs in core markets.",
    },
    "it_process_automation": {
        GeoZone.MIDWEST: ServiceEligibility.ON_SITE,
        GeoZone.NORTH_FLORIDA: ServiceEligibility.ON_SITE,
        GeoZone.REMOTE_NA: ServiceEligibility.REMOTE_ONLY,
        "notes": "Automation work is inherently remote. On-site discovery preferred.",
    },
    "voip": {
        GeoZone.MIDWEST: ServiceEligibility.ON_SITE,
        GeoZone.NORTH_FLORIDA: ServiceEligibility.ON_SITE,
        GeoZone.REMOTE_NA: ServiceEligibility.REMOTE_ONLY,
        "notes": "Cloud VOIP is remote. On-site for handset deployment in core markets.",
    },
    "wfh_implementation": {
        GeoZone.MIDWEST: ServiceEligibility.ON_SITE,
        GeoZone.NORTH_FLORIDA: ServiceEligibility.ON_SITE,
        GeoZone.REMOTE_NA: ServiceEligibility.REMOTE_ONLY,
        "notes": "WFH setup is remote by nature. On-site for endpoint deployment.",
    },
}


# ---------------------------------------------------------------------------
# Geo Routing Helper Data
# ---------------------------------------------------------------------------

def is_midwest(state_code: str) -> bool:
    """Check if a US state code is in the Midwest territory."""
    return state_code.upper() in MIDWEST_STATE_CODES


def is_north_florida(zip_code: str) -> bool:
    """Check if a US zip code falls in Northern Florida territory."""
    if not zip_code or len(zip_code) < 3:
        return False
    return zip_code[:3] in NORTH_FLORIDA_ZIP_PREFIXES


def get_geo_zone(state_code: str = "", zip_code: str = "", country: str = "US") -> GeoZone:
    """Determine the GeoZone for a given location."""
    state_code = state_code.upper()
    country = country.upper()

    if country not in NORTH_AMERICA_COUNTRIES:
        return GeoZone.REMOTE_NA  # Outside NA still gets remote classification

    if state_code in MIDWEST_STATE_CODES:
        return GeoZone.MIDWEST

    if state_code == "FL" and is_north_florida(zip_code):
        return GeoZone.NORTH_FLORIDA

    return GeoZone.REMOTE_NA


def get_service_eligibility(service_id: str, geo_zone: GeoZone) -> ServiceEligibility:
    """Get eligibility for a service in a given geo zone."""
    service = SERVICE_GEO_ELIGIBILITY.get(service_id, {})
    return service.get(geo_zone, ServiceEligibility.NOT_AVAILABLE)


def get_eligible_services(state_code: str = "", zip_code: str = "", country: str = "US") -> dict:
    """Get all eligible services and their delivery mode for a location."""
    zone = get_geo_zone(state_code, zip_code, country)
    result = {}
    for service_id, zones in SERVICE_GEO_ELIGIBILITY.items():
        eligibility = zones.get(zone, ServiceEligibility.NOT_AVAILABLE)
        if eligibility != ServiceEligibility.NOT_AVAILABLE:
            result[service_id] = {
                "eligibility": eligibility,
                "geo_zone": zone,
                "notes": zones.get("notes", ""),
            }
    return result


# ---------------------------------------------------------------------------
# Composite export
# ---------------------------------------------------------------------------

GEO_ROUTING = {
    "zones": {
        "midwest": {
            "states": MIDWEST_STATES,
            "state_codes": MIDWEST_STATE_CODES,
            "description": "Primary on-site territory. Full service catalog available.",
        },
        "north_florida": {
            "zip_prefixes": NORTH_FLORIDA_ZIP_PREFIXES,
            "metros": NORTH_FLORIDA_METROS,
            "state": "FL",
            "description": "Secondary on-site territory. Full service catalog available.",
        },
        "remote_na": {
            "countries": NORTH_AMERICA_COUNTRIES,
            "us_states": ALL_US_STATES,
            "ca_provinces": CANADIAN_PROVINCES,
            "description": "Remote-only territory. Cybersecurity, monitoring, vCIO, and automation available.",
        },
    },
    "service_eligibility": SERVICE_GEO_ELIGIBILITY,
    "helpers": {
        "is_midwest": is_midwest,
        "is_north_florida": is_north_florida,
        "get_geo_zone": get_geo_zone,
        "get_service_eligibility": get_service_eligibility,
        "get_eligible_services": get_eligible_services,
    },
    "prospecting_priority": {
        "tier_1": "Midwest primary states (IL, IN, WI) - highest density, fastest on-site response",
        "tier_2": "Midwest secondary states + North Florida metros",
        "tier_3": "All North America for remote-eligible services",
    },
}
