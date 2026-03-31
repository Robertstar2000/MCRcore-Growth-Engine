"""
MCRcore Growth Engine - ICP Targeting Skill

Converts ICP rules into actionable filters, search queries,
title-to-buying-role mappings, and geo routing rules.
Also provides a composite score_icp_fit() for evaluating a
company+contact pair against the Ideal Customer Profile.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from config.icp_rules import (
    COMPANY_SIZE_BANDS,
    EXCLUSION_RULES,
    TARGET_INDUSTRIES,
    TITLE_PATTERNS,
    TITLE_PRIORITY_MAP,
    BuyingRole,
    ICP_RULES,
    IndustryPriority,
    SizeBand,
)


# ---------------------------------------------------------------------------
# Search filter generation
# ---------------------------------------------------------------------------

def build_search_filters() -> Dict[str, Any]:
    """
    Convert ICP rules into a structured filter dict suitable for
    driving external search APIs (LinkedIn, Apollo, ZoomInfo, etc.).

    Returns a dict with keys:
        size_filter   - min/max employee counts
        industries    - list of target industry keyword groups
        titles        - list of target titles (canonical)
        geo           - geographic targeting rules
        exclusions    - exclusion criteria
    """
    # Size
    min_emp = min(b["min_employees"] for b in COMPANY_SIZE_BANDS.values())
    max_emp = max(b["max_employees"] for b in COMPANY_SIZE_BANDS.values())

    # Collect industry keywords (flattened)
    industry_kw_groups = {}
    for ind_key, ind_val in TARGET_INDUSTRIES.items():
        industry_kw_groups[ind_key] = {
            "label": ind_val["label"],
            "keywords": ind_val.get("keywords", []),
            "priority": ind_val["priority"].value,
        }

    # Titles
    title_list = list(TITLE_PRIORITY_MAP.keys())

    return {
        "size_filter": {
            "min_employees": min_emp,
            "max_employees": max_emp,
        },
        "industries": industry_kw_groups,
        "titles": title_list,
        "geo": get_geo_rules(),
        "exclusions": get_exclusion_rules(),
    }


def generate_search_queries(source_type: str = "linkedin") -> List[str]:
    """
    Generate example search query strings for a given source type.

    Args:
        source_type: One of 'linkedin', 'apollo', 'google', 'zoominfo'.

    Returns:
        List of query strings.
    """
    queries: List[str] = []

    # Collect high-value industry keywords
    p1_keywords: List[str] = []
    for ind_key, ind_val in TARGET_INDUSTRIES.items():
        if ind_val["priority"] == IndustryPriority.P1:
            p1_keywords.extend(ind_val.get("keywords", [])[:3])

    # Collect top titles
    top_titles = [
        t for t, info in TITLE_PRIORITY_MAP.items()
        if info["priority"] <= 2
    ]

    if source_type == "linkedin":
        for title in top_titles[:5]:
            for kw in p1_keywords[:4]:
                queries.append(f'"{title}" AND "{kw}"')
    elif source_type == "apollo":
        for title in top_titles[:5]:
            queries.append(f"title={title}")
    elif source_type == "google":
        for kw in p1_keywords[:6]:
            queries.append(
                f'site:linkedin.com/in/ "{kw}" '
                f'("Owner" OR "CEO" OR "CTO" OR "IT Director")'
            )
    else:
        # Generic
        for title in top_titles[:5]:
            queries.append(f"{title} {' OR '.join(p1_keywords[:3])}")

    return queries


# ---------------------------------------------------------------------------
# Title / buying-role mapping
# ---------------------------------------------------------------------------

def get_title_map() -> Dict[str, Dict[str, Any]]:
    """
    Return the full title-to-buying-role map, enriched with
    canonical title and string role labels.
    """
    result: Dict[str, Dict[str, Any]] = {}
    for title, info in TITLE_PRIORITY_MAP.items():
        result[title] = {
            "priority": info["priority"],
            "score": info["score"],
            "buying_role": info["buying_role"].value,
        }
    return result


def match_title_to_canonical(raw_title: str) -> Optional[str]:
    """
    Attempt to normalise a raw title string to one of the canonical
    titles using the TITLE_PATTERNS regex list.

    Returns:
        Canonical title string or None if no match.
    """
    if not raw_title:
        return None

    # Exact match first (case-insensitive)
    for canonical in TITLE_PRIORITY_MAP:
        if raw_title.strip().lower() == canonical.lower():
            return canonical

    # Regex pattern match
    for pattern, canonical in TITLE_PATTERNS:
        if re.search(pattern, raw_title):
            return canonical

    return None


def get_buying_role(title: str) -> Optional[str]:
    """Return the buying role string for a given canonical or raw title."""
    canonical = match_title_to_canonical(title) or title
    info = TITLE_PRIORITY_MAP.get(canonical)
    if info:
        return info["buying_role"].value
    return None


# ---------------------------------------------------------------------------
# Geo routing
# ---------------------------------------------------------------------------

def get_geo_rules() -> Dict[str, Any]:
    """
    Return geographic targeting/routing rules.

    MCRcore primarily targets:
      - Dallas-Fort Worth metro (local / on-site capable)
      - Texas state-wide (remote-first, occasional on-site)
      - National (remote-only managed services)
    """
    return {
        "primary_geo": "Dallas-Fort Worth, TX",
        "tiers": {
            "tier_1": {
                "label": "DFW Metro",
                "radius_miles": 60,
                "fit_bonus": 15,
                "on_site_capable": True,
            },
            "tier_2": {
                "label": "Texas Statewide",
                "states": ["TX"],
                "fit_bonus": 8,
                "on_site_capable": False,
            },
            "tier_3": {
                "label": "National (Remote)",
                "states": [],  # all US
                "fit_bonus": 0,
                "on_site_capable": False,
            },
        },
    }


# ---------------------------------------------------------------------------
# Exclusion rules
# ---------------------------------------------------------------------------

def get_exclusion_rules() -> Dict[str, Any]:
    """Return the full exclusion rule set as a plain dict."""
    return dict(EXCLUSION_RULES)


def is_excluded(
    company_data: Dict[str, Any],
    contact_data: Dict[str, Any] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Check whether a company/contact should be excluded.

    Returns:
        (is_excluded: bool, reason: str | None)
    """
    rules = EXCLUSION_RULES
    contact_data = contact_data or {}

    # Company name denylist
    company_name = (company_data.get("company_name") or "").lower()
    for denied in rules.get("company_denylist", []):
        if denied.lower() in company_name:
            return True, f"Company in denylist: {denied}"

    # Industry exclusion
    industry = (company_data.get("industry") or "").lower()
    for exc_ind in rules.get("excluded_industries", []):
        if exc_ind.lower() in industry:
            return True, f"Excluded industry: {exc_ind}"

    # Keyword exclusion
    summary = (company_data.get("summary") or "").lower()
    for kw in rules.get("excluded_keywords", []):
        if kw.lower() in summary or kw.lower() in company_name:
            return True, f"Excluded keyword: {kw}"

    # Title exclusion
    title = (contact_data.get("title") or "").lower()
    for exc_title in rules.get("excluded_titles", []):
        if exc_title.lower() in title:
            return True, f"Excluded title: {exc_title}"

    # Email domain denylist
    email = (contact_data.get("email") or "")
    if "@" in email:
        domain = email.split("@", 1)[1].lower()
        if domain in [d.lower() for d in rules.get("email_domain_denylist", [])]:
            return True, f"Personal email domain: {domain}"

    # Employee count
    emp_str = company_data.get("employee_band") or company_data.get("employee_count")
    if emp_str is not None:
        try:
            # Handle band strings like "50-200"
            if isinstance(emp_str, str) and "-" in emp_str:
                emp_count = int(emp_str.split("-")[1])
            else:
                emp_count = int(emp_str)
            min_e = rules["company_size"]["min_employees"]
            max_e = rules["company_size"]["max_employees"]
            if emp_count < min_e:
                return True, f"Too small: {emp_count} < {min_e}"
            if emp_count > max_e:
                return True, f"Too large: {emp_count} > {max_e}"
        except (ValueError, TypeError):
            pass  # Can't parse — don't exclude

    return False, None


# ---------------------------------------------------------------------------
# Composite ICP fit scoring
# ---------------------------------------------------------------------------

def score_icp_fit(
    company_data: Dict[str, Any],
    contact_data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Score how well a company + contact pair fits the Ideal Customer Profile.

    Args:
        company_data: Dict with keys like company_name, industry,
                      employee_band, geography, summary.
        contact_data: Dict with keys like title, email.

    Returns:
        {
            "total_score": float (0-100),
            "component_scores": { ... },
            "excluded": bool,
            "exclusion_reason": str | None,
            "qualified": bool,
            "high_priority": bool,
            "matched_industry": str | None,
            "buying_role": str | None,
        }
    """
    contact_data = contact_data or {}
    weights = ICP_RULES["scoring"]["weights"]

    # Check exclusions first
    excluded, reason = is_excluded(company_data, contact_data)
    if excluded:
        return {
            "total_score": 0.0,
            "component_scores": {},
            "excluded": True,
            "exclusion_reason": reason,
            "qualified": False,
            "high_priority": False,
            "matched_industry": None,
            "buying_role": None,
        }

    components: Dict[str, float] = {}

    # ---- Company size score ----
    size_score = 0.0
    emp_str = company_data.get("employee_band") or ""
    for band_enum, band_info in COMPANY_SIZE_BANDS.items():
        band_label = band_enum.value
        if band_label in emp_str.lower():
            size_score = band_info["fit_score"]
            break
    if size_score == 0.0 and emp_str:
        # Try numeric parsing
        try:
            if "-" in str(emp_str):
                low, high = str(emp_str).split("-")
                mid = (int(low) + int(high)) / 2
            else:
                mid = float(emp_str)
            for band_enum, band_info in COMPANY_SIZE_BANDS.items():
                if band_info["min_employees"] <= mid <= band_info["max_employees"]:
                    size_score = band_info["fit_score"]
                    break
        except (ValueError, TypeError):
            size_score = 50.0  # Unknown — give partial credit
    components["company_size"] = size_score

    # ---- Industry fit score ----
    industry_score = 0.0
    matched_industry = None
    company_text = " ".join([
        company_data.get("industry", ""),
        company_data.get("summary", ""),
        company_data.get("company_name", ""),
    ]).lower()

    for ind_key, ind_val in TARGET_INDUSTRIES.items():
        for kw in ind_val.get("keywords", []):
            if kw.lower() in company_text:
                bonus = ind_val.get("fit_score_bonus", 0)
                candidate_score = 50 + bonus  # base 50 + bonus
                if candidate_score > industry_score:
                    industry_score = candidate_score
                    matched_industry = ind_key
                break
    components["industry_fit"] = min(industry_score, 100.0)

    # ---- Title score ----
    title_score = 0.0
    buying_role = None
    raw_title = contact_data.get("title", "")
    if raw_title:
        canonical = match_title_to_canonical(raw_title)
        if canonical and canonical in TITLE_PRIORITY_MAP:
            info = TITLE_PRIORITY_MAP[canonical]
            title_score = info["score"]
            buying_role = info["buying_role"].value
        else:
            title_score = 30.0  # Unknown title — low partial credit
    components["title_score"] = title_score

    # ---- Geo fit score ----
    geo_score = 50.0  # default if unknown
    geography = (company_data.get("geography") or "").lower()
    if "dallas" in geography or "dfw" in geography or "fort worth" in geography:
        geo_score = 100.0
    elif "texas" in geography or ", tx" in geography:
        geo_score = 75.0
    elif geography:
        geo_score = 40.0  # National / out-of-state
    components["geo_fit"] = geo_score

    # ---- Engagement signals (placeholder — no engagement data here) ----
    components["engagement_signals"] = 0.0  # Scored elsewhere

    # ---- Weighted total ----
    total = sum(
        components.get(key, 0.0) * weight
        for key, weight in weights.items()
    )
    total = min(total, 100.0)

    thresholds = ICP_RULES["scoring"]

    return {
        "total_score": round(total, 2),
        "component_scores": components,
        "excluded": False,
        "exclusion_reason": None,
        "qualified": total >= thresholds["qualified_threshold"],
        "high_priority": total >= thresholds["high_priority_threshold"],
        "matched_industry": matched_industry,
        "buying_role": buying_role,
    }
