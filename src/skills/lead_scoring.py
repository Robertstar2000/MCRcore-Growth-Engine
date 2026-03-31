"""
MCRcore Growth Engine - Lead Scoring Skill

Weighted scoring model definition, probability bands, tie-break logic,
and override rules. Pure functions with no DB dependency.
"""

from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Weight Model: overall probability calculation
# ---------------------------------------------------------------------------

OVERALL_WEIGHTS = {
    "fit": 0.30,
    "need": 0.25,
    "package_fit": 0.20,
    "engagement": 0.15,
    "margin": 0.10,
}


# ---------------------------------------------------------------------------
# Fit Score Component Weights (sum to 1.0)
# ---------------------------------------------------------------------------

FIT_WEIGHTS = {
    "employee_size_fit": 0.25,
    "industry_fit": 0.25,
    "geo_fit": 0.20,
    "title_fit": 0.15,
    "erp_evidence": 0.10,
    "managed_service_suitability": 0.05,
}


# ---------------------------------------------------------------------------
# Need Score Component Weights (sum to 1.0)
# ---------------------------------------------------------------------------

NEED_WEIGHTS = {
    "support_complexity": 0.20,
    "compliance_burden": 0.20,
    "remote_hybrid_need": 0.15,
    "uptime_sensitivity": 0.15,
    "growth_strain": 0.15,
    "weak_internal_it": 0.15,
}


# ---------------------------------------------------------------------------
# Engagement Score Component Weights (sum to 1.0)
# ---------------------------------------------------------------------------

ENGAGEMENT_WEIGHTS = {
    "open": 0.10,
    "click": 0.15,
    "reply": 0.25,
    "positive_language": 0.15,
    "price_request": 0.15,
    "audit_request": 0.10,
    "stakeholder_referral": 0.10,
}


# ---------------------------------------------------------------------------
# Margin Band Scores
# ---------------------------------------------------------------------------

MARGIN_BAND_SCORES = {
    "high": 100,
    "medium": 75,
    "low-wedge": 50,
    "tentative": 30,
    "variable": 60,
}

# Map service IDs to margin band labels for scoring
SERVICE_MARGIN_MAP = {
    "total_plan": "high",
    "proactive_monitoring": "high",
    "essential_cybersecurity": "low-wedge",
    "virtual_servers": "medium",
    "fractional_cio": "high",
    "it_process_automation": "high",
    "wfh_implementation": "medium",
    "voip": "medium",
    "on_demand_break_fix": "tentative",
    "technical_audit": "variable",
}


# ---------------------------------------------------------------------------
# Priority Tier Thresholds
# ---------------------------------------------------------------------------

PRIORITY_TIERS = {
    "tier1": {"min": 80, "max": 100, "label": "Tier 1 - Hot Prospect"},
    "tier2": {"min": 60, "max": 79, "label": "Tier 2 - Warm Prospect"},
    "tier3": {"min": 40, "max": 59, "label": "Tier 3 - Nurture"},
    "tier4": {"min": 0, "max": 39, "label": "Tier 4 - Long-term / Monitor"},
}


# ---------------------------------------------------------------------------
# Override Rules
# ---------------------------------------------------------------------------

OVERRIDE_RULES = {
    "opt_out_suppress": {
        "description": "Opt-out flag suppresses all scoring and outreach",
        "effect": "suppress",
    },
    "invalid_email_suppress": {
        "description": "Invalid or bounced email suppresses lead",
        "effect": "suppress",
    },
    "inbound_quote_boost": {
        "description": "Inbound quote request = high priority override",
        "effect": "boost_to_tier1",
        "min_probability": 85,
    },
    "tallman_referral_boost": {
        "description": "Tallman referral = boosted priority",
        "effect": "boost_probability",
        "boost_amount": 15,
    },
    "midwest_manufacturing_epicor": {
        "description": "Midwest manufacturing + Epicor = package fit boost",
        "effect": "boost_package_fit",
        "boost_amount": 20,
    },
}


# ---------------------------------------------------------------------------
# Pure Scoring Functions
# ---------------------------------------------------------------------------

def calculate_weighted_score(
    components: Dict[str, float],
    weights: Dict[str, float],
) -> float:
    """
    Calculate a weighted score from component values and weights.

    Args:
        components: Dict of {component_name: score (0-100)}.
        weights: Dict of {component_name: weight (sums to ~1.0)}.

    Returns:
        Weighted score (0-100).
    """
    total = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        value = components.get(key, 0.0)
        total += value * weight
        weight_sum += weight
    # Normalize in case weights don't sum exactly to 1.0
    if weight_sum > 0:
        return (total / weight_sum) * 1.0
    return 0.0


def calculate_overall_probability(
    fit_score: float,
    need_score: float,
    engagement_score: float,
    package_fit_score: float,
    margin_score: float,
) -> float:
    """
    Calculate overall sales probability from sub-scores.

    Returns a probability score 0-100.
    """
    components = {
        "fit": fit_score,
        "need": need_score,
        "engagement": engagement_score,
        "package_fit": package_fit_score,
        "margin": margin_score,
    }
    return calculate_weighted_score(components, OVERALL_WEIGHTS)


def assign_priority_tier(probability: float) -> str:
    """
    Map a probability score to a priority tier.

    Returns: 'tier1', 'tier2', 'tier3', or 'tier4'.
    """
    if probability >= 80:
        return "tier1"
    elif probability >= 60:
        return "tier2"
    elif probability >= 40:
        return "tier3"
    else:
        return "tier4"


def get_margin_band_for_service(service_id: str) -> str:
    """Get the margin band label for a service ID."""
    return SERVICE_MARGIN_MAP.get(service_id, "variable")


def get_margin_score(margin_band: str) -> float:
    """Convert a margin band label to a numeric score (0-100)."""
    return float(MARGIN_BAND_SCORES.get(margin_band, 50))


def apply_override_rules(
    lead_data: Dict[str, Any],
    probability: float,
    package_fit_score: float,
) -> Tuple[float, float, Optional[str]]:
    """
    Apply override rules that can modify probability and package fit scores.

    Args:
        lead_data: Dict with keys: opt_out, email_valid, inbound_quote,
                   tallman_referral, midwest, manufacturing, epicor.
        probability: Current probability score.
        package_fit_score: Current package fit score.

    Returns:
        (adjusted_probability, adjusted_package_fit, suppress_reason or None)
    """
    # Opt-out suppresses everything
    if lead_data.get("opt_out", False):
        return 0.0, 0.0, "opt_out_suppress"

    # Invalid email suppresses
    if lead_data.get("email_valid") is False:
        return 0.0, 0.0, "invalid_email_suppress"

    # Inbound quote request = tier 1
    if lead_data.get("inbound_quote", False):
        probability = max(probability, OVERRIDE_RULES["inbound_quote_boost"]["min_probability"])

    # Tallman referral boost
    if lead_data.get("tallman_referral", False):
        probability = min(100.0, probability + OVERRIDE_RULES["tallman_referral_boost"]["boost_amount"])

    # Midwest manufacturing + Epicor boost
    if (
        lead_data.get("midwest", False)
        and lead_data.get("manufacturing", False)
        and lead_data.get("epicor", False)
    ):
        package_fit_score = min(
            100.0,
            package_fit_score + OVERRIDE_RULES["midwest_manufacturing_epicor"]["boost_amount"],
        )

    return probability, package_fit_score, None


def tie_break_leads(
    leads: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Break ties between leads with the same probability score.

    Tie-break order:
      1. Higher fit_score
      2. Higher engagement_score
      3. Higher margin band score
      4. On-site territory preferred over remote
      5. Newer lead (more recent created_at)

    Args:
        leads: List of dicts with scoring data. Each dict must have:
               probability, fit_score, engagement_score, margin_score,
               on_site_territory (bool), created_at (ISO string).

    Returns:
        Sorted list (highest priority first).
    """
    def sort_key(lead):
        return (
            lead.get("probability", 0),
            lead.get("fit_score", 0),
            lead.get("engagement_score", 0),
            lead.get("margin_score", 0),
            1 if lead.get("on_site_territory", False) else 0,
            lead.get("created_at", ""),
        )

    return sorted(leads, key=sort_key, reverse=True)


def score_employee_size_fit(employee_count: Optional[int]) -> float:
    """Score 0-100 for employee count fit to MCRcore ICP."""
    if employee_count is None:
        return 30.0  # Unknown = modest default
    if employee_count < 3:
        return 0.0  # Too small
    if employee_count > 200:
        return 10.0  # Too large for MSP model
    if 25 <= employee_count <= 50:
        return 100.0  # Sweet spot
    if 50 < employee_count <= 200:
        return 85.0
    if 10 <= employee_count < 25:
        return 70.0
    if 3 <= employee_count < 10:
        return 50.0
    return 30.0


def score_industry_fit(industry: Optional[str], industry_config: Dict[str, Any]) -> float:
    """
    Score 0-100 for industry fit.

    Args:
        industry: Industry string from company record.
        industry_config: TARGET_INDUSTRIES dict from icp_rules.
    """
    if not industry:
        return 20.0
    industry_lower = industry.lower()
    for key, cfg in industry_config.items():
        keywords = cfg.get("keywords", [])
        if any(kw.lower() in industry_lower for kw in keywords):
            # P1 industries score higher
            priority = cfg.get("priority")
            if priority and priority.value == 1:
                return 90.0 + cfg.get("fit_score_bonus", 0) / 10.0
            else:
                return 70.0 + cfg.get("fit_score_bonus", 0) / 10.0
    return 30.0


def score_geo_fit(geo_zone_value: str) -> float:
    """Score 0-100 for geographic fit."""
    if geo_zone_value == "midwest":
        return 100.0
    elif geo_zone_value == "north_florida":
        return 90.0
    elif geo_zone_value == "remote_north_america":
        return 50.0
    return 20.0


def score_title_fit(title: Optional[str], title_map: Dict[str, Any]) -> float:
    """Score 0-100 for contact title fit."""
    if not title:
        return 20.0
    # Direct match
    if title in title_map:
        return float(title_map[title].get("score", 50))
    # Partial match
    title_lower = title.lower()
    for canonical, data in title_map.items():
        if canonical.lower() in title_lower:
            return float(data.get("score", 50))
    return 25.0


def score_erp_evidence(
    erp_signals_text: Optional[str],
    epicor_signal: float = 0.0,
    mcleod_signal: float = 0.0,
) -> float:
    """Score 0-100 for ERP evidence strength."""
    score = 0.0
    if epicor_signal >= 0.7:
        score = max(score, 100.0)
    elif epicor_signal >= 0.5:
        score = max(score, 80.0)
    if mcleod_signal >= 0.7:
        score = max(score, 95.0)
    elif mcleod_signal >= 0.5:
        score = max(score, 75.0)
    if erp_signals_text:
        erp_lower = erp_signals_text.lower()
        if any(kw in erp_lower for kw in ["epicor", "p21", "prophet 21"]):
            score = max(score, 85.0)
        if any(kw in erp_lower for kw in ["mcleod", "dat", "keypoint"]):
            score = max(score, 80.0)
        if any(kw in erp_lower for kw in ["sap", "erp", "sage"]):
            score = max(score, 60.0)
    return score


def score_managed_service_suitability(
    employee_count: Optional[int],
    has_it_staff: bool = False,
) -> float:
    """Score 0-100 for how suitable this company is for managed services."""
    if employee_count is None:
        return 40.0
    # Sweet spot: no IT staff, 10-100 employees
    if not has_it_staff and 10 <= employee_count <= 100:
        return 100.0
    if not has_it_staff and employee_count < 10:
        return 70.0
    if has_it_staff and 50 <= employee_count <= 200:
        return 60.0  # Augmentation play
    if has_it_staff and employee_count < 50:
        return 40.0  # May not need full managed
    return 30.0
