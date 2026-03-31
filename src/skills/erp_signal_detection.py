"""
MCRcore Growth Engine - ERP / Industry Signal Detection Skill

Contains keyword sets for each tracked ERP system, industry keyword groups,
weighted-evidence scoring, and confidence-label mappings.  Used by agents
(primarily ERPSignalAgent) to turn raw text into scored signal floats.
"""

from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# ERP Keyword Sets
# ---------------------------------------------------------------------------

_ERP_KEYWORDS: Dict[str, Dict] = {
    "epicor": {
        "label": "Epicor Prophet 21",
        "keywords": [
            "epicor", "prophet 21", "prophet21", "p21",
            "epicor erp", "epicor prophet", "epicor p21",
        ],
        "weight": 1.0,  # base weight per keyword hit
        "strong_keywords": ["prophet 21", "prophet21", "epicor p21"],
        "strong_weight": 1.5,
    },
    "por": {
        "label": "Point of Rental",
        "keywords": [
            "point of rental", "por", "point-of-rental",
            "rental management software", "por software",
        ],
        "weight": 1.0,
        "strong_keywords": ["point of rental", "point-of-rental"],
        "strong_weight": 1.5,
    },
    "mcleod": {
        "label": "McLeod Software",
        "keywords": [
            "mcleod", "loadmaster", "mcleod software", "mcleod loadmaster",
            "mcleod tms", "powerbroker",
        ],
        "weight": 1.0,
        "strong_keywords": ["mcleod software", "mcleod loadmaster", "powerbroker"],
        "strong_weight": 1.5,
    },
    "dat_keypoint": {
        "label": "DAT Keypoint",
        "keywords": [
            "dat", "keypoint", "dat keypoint", "dat solutions",
            "dat freight", "dat power",
        ],
        "weight": 0.8,   # "dat" alone is common — lower base weight
        "strong_keywords": ["dat keypoint", "dat solutions"],
        "strong_weight": 1.5,
    },
}

# ---------------------------------------------------------------------------
# Industry Keyword Sets
# ---------------------------------------------------------------------------

_INDUSTRY_KEYWORDS: Dict[str, Dict] = {
    "manufacturing": {
        "label": "Manufacturing",
        "keywords": [
            "manufacturing", "fabricat", "machining", "assembly",
            "CNC", "industrial", "OEM", "plant", "production line",
            "shop floor", "tooling", "stamping",
        ],
        "weight": 1.0,
        "strong_keywords": ["manufacturing", "fabrication", "machining"],
        "strong_weight": 1.3,
    },
    "logistics": {
        "label": "Freight & Logistics",
        "keywords": [
            "freight", "logistics", "shipping", "warehouse", "3pl",
            "trucking", "LTL", "FTL", "carrier", "fleet",
            "brokerage", "transportation management",
        ],
        "weight": 1.0,
        "strong_keywords": ["freight", "logistics", "3pl", "trucking"],
        "strong_weight": 1.3,
    },
    "insurance": {
        "label": "Insurance",
        "keywords": [
            "insurance", "underwriting", "claims", "policy admin",
            "risk management", "agency management", "broker",
            "insured", "premium", "actuary",
        ],
        "weight": 1.0,
        "strong_keywords": ["insurance", "underwriting", "claims", "policy admin"],
        "strong_weight": 1.3,
    },
    "scaling": {
        "label": "Scaling SMB",
        "keywords": [
            "scaling", "growing company", "rapid growth", "expansion",
            "Series A", "Series B", "venture", "startup to scaleup",
            "hiring spree", "new offices",
        ],
        "weight": 0.9,
        "strong_keywords": ["scaling", "rapid growth", "Series A"],
        "strong_weight": 1.3,
    },
}

# ---------------------------------------------------------------------------
# Confidence Label Thresholds
# ---------------------------------------------------------------------------

_CONFIDENCE_THRESHOLDS: List[Tuple[float, str]] = [
    (0.6, "high"),
    (0.3, "medium"),
    (0.0, "low"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_erp_keywords() -> Dict[str, Dict]:
    """Return the full ERP keyword registry (deep copy safe)."""
    return dict(_ERP_KEYWORDS)


def get_industry_keywords() -> Dict[str, Dict]:
    """Return the full industry keyword registry."""
    return dict(_INDUSTRY_KEYWORDS)


def calculate_weighted_evidence(
    matches: Dict[str, List[str]],
    keyword_registry: Dict[str, Dict] = None,
) -> Dict[str, float]:
    """
    Given a dict of {signal_key: [matched_keywords, ...]}, calculate a
    weighted confidence score (0.0-1.0) for each signal.

    The scoring approach:
      1. Each normal keyword hit adds `weight` points.
      2. Each strong keyword hit adds `strong_weight` points instead.
      3. Raw score is clamped and normalised to 0.0-1.0 with a soft
         ceiling at 5.0 raw points (i.e. 5 pts => 1.0).

    Args:
        matches: {signal_key: [keyword_hit_1, keyword_hit_2, ...]}
        keyword_registry: The keyword dict to use for weights.
                          Falls back to merged ERP + industry.

    Returns:
        {signal_key: confidence_float}
    """
    if keyword_registry is None:
        keyword_registry = {**_ERP_KEYWORDS, **_INDUSTRY_KEYWORDS}

    scores: Dict[str, float] = {}
    max_raw = 5.0  # soft ceiling for normalisation

    for signal_key, hit_list in matches.items():
        reg = keyword_registry.get(signal_key, {})
        base_w = reg.get("weight", 1.0)
        strong_w = reg.get("strong_weight", 1.5)
        strong_set = {kw.lower() for kw in reg.get("strong_keywords", [])}

        raw = 0.0
        for kw in hit_list:
            if kw.lower() in strong_set:
                raw += strong_w
            else:
                raw += base_w

        # Normalise: 0-max_raw → 0.0-1.0, clamped
        scores[signal_key] = min(raw / max_raw, 1.0)

    return scores


def get_confidence_label(score: float) -> str:
    """
    Map a 0.0-1.0 confidence float to a human-readable label.

    Thresholds:
        0.0 - 0.3  -> 'low'
        0.3 - 0.6  -> 'medium'
        0.6 - 1.0  -> 'high'
    """
    for threshold, label in _CONFIDENCE_THRESHOLDS:
        if score >= threshold:
            return label
    return "low"
