"""
MCRcore Growth Engine - Ideal Customer Profile (ICP) Targeting Rules
Defines company size bands, industry priorities, geographic rules,
title/buying-role mapping, and exclusion criteria.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Company Size Bands
# ---------------------------------------------------------------------------

class SizeBand(Enum):
    MICRO = "micro"          # 3-25 employees
    SMALL = "small"          # 25-50 employees
    MID = "mid"              # 50-200 employees


COMPANY_SIZE_BANDS = {
    SizeBand.MICRO: {
        "label": "Micro (3-25 employees)",
        "min_employees": 3,
        "max_employees": 25,
        "fit_score": 70,
        "notes": "Often owner-led IT decisions. Quick sales cycles. "
                 "High affinity for Essential Cybersecurity + Proactive Monitoring.",
    },
    SizeBand.SMALL: {
        "label": "Small (25-50 employees)",
        "min_employees": 25,
        "max_employees": 50,
        "fit_score": 90,
        "notes": "Sweet spot. Outgrowing DIY IT but not ready for full-time staff. "
                 "Total Plan + Fractional CIO upsell.",
    },
    SizeBand.MID: {
        "label": "Mid (50-200 employees)",
        "min_employees": 50,
        "max_employees": 200,
        "fit_score": 85,
        "notes": "May have 1-2 IT staff needing augmentation. "
                 "ERP, compliance, and process automation needs.",
    },
}


# ---------------------------------------------------------------------------
# Industry Targeting
# ---------------------------------------------------------------------------

class IndustryPriority(Enum):
    P1 = 1  # Priority 1 - primary verticals
    P2 = 2  # Priority 2 - secondary / horizontal traits


TARGET_INDUSTRIES = {
    # ---- Priority 1: Named Verticals ----
    "manufacturing": {
        "priority": IndustryPriority.P1,
        "label": "Manufacturing",
        "fit_score_bonus": 20,
        "keywords": [
            "manufacturing", "fabrication", "machining", "CNC",
            "industrial", "OEM", "contract manufacturer",
        ],
        "naics_prefixes": ["31", "32", "33"],
        "erp_affinity": ["Epicor P21", "Prophet 21", "SAP Business One"],
        "pain_points": [
            "Legacy ERP systems with no IT support",
            "Cybersecurity gaps on shop-floor OT/IT convergence",
            "Compliance requirements (CMMC, NIST, ITAR)",
        ],
    },
    "supply_chain": {
        "priority": IndustryPriority.P1,
        "label": "Supply Chain & Distribution",
        "fit_score_bonus": 18,
        "keywords": [
            "supply chain", "distribution", "wholesale", "warehousing",
            "3PL", "fulfillment",
        ],
        "naics_prefixes": ["42", "48", "49"],
        "erp_affinity": ["Epicor P21", "Prophet 21"],
        "pain_points": [
            "Multi-site connectivity and uptime",
            "Inventory system reliability",
            "WMS/ERP integration fragility",
        ],
    },
    "freight_logistics": {
        "priority": IndustryPriority.P1,
        "label": "Freight & Logistics",
        "fit_score_bonus": 20,
        "keywords": [
            "freight", "logistics", "trucking", "LTL", "FTL",
            "brokerage", "carrier", "fleet",
        ],
        "naics_prefixes": ["484", "488"],
        "erp_affinity": ["McLeod Software", "DAT Keypoint", "TMW"],
        "pain_points": [
            "McLeod/DAT support gaps after vendor changes",
            "Driver communication and mobile IT",
            "Cybersecurity for EDI and load-board integrations",
        ],
    },
    "insurance": {
        "priority": IndustryPriority.P1,
        "label": "Insurance",
        "fit_score_bonus": 15,
        "keywords": [
            "insurance", "agency", "broker", "underwriting",
            "claims", "risk management",
        ],
        "naics_prefixes": ["524"],
        "erp_affinity": [],
        "pain_points": [
            "Compliance and data-protection mandates",
            "Remote workforce security",
            "Aging agency management systems",
        ],
    },
    "scaling_smb": {
        "priority": IndustryPriority.P1,
        "label": "Scaling SMBs (general)",
        "fit_score_bonus": 10,
        "keywords": [
            "growing company", "scaling", "Series A", "expansion",
        ],
        "naics_prefixes": [],
        "erp_affinity": [],
        "pain_points": [
            "No dedicated IT team",
            "Ad-hoc tech decisions creating tech debt",
            "Need strategic IT roadmap",
        ],
    },

    # ---- Priority 2: Horizontal Traits ----
    "multi_site": {
        "priority": IndustryPriority.P2,
        "label": "Multi-Site Operations",
        "fit_score_bonus": 12,
        "keywords": ["multi-site", "multi-location", "branch offices"],
        "trait": True,
        "pain_points": [
            "Inconsistent IT standards across locations",
            "WAN/SD-WAN complexity",
            "Centralized monitoring needs",
        ],
    },
    "compliance_sensitive": {
        "priority": IndustryPriority.P2,
        "label": "Compliance-Sensitive",
        "fit_score_bonus": 12,
        "keywords": [
            "HIPAA", "CMMC", "SOC2", "PCI-DSS", "NIST",
            "regulated", "compliance", "audit",
        ],
        "trait": True,
        "pain_points": [
            "Audit readiness gaps",
            "Documentation and policy enforcement",
            "Vendor risk management",
        ],
    },
    "remote_hybrid": {
        "priority": IndustryPriority.P2,
        "label": "Remote / Hybrid Workforce",
        "fit_score_bonus": 8,
        "keywords": [
            "remote", "hybrid", "work from home", "WFH",
            "distributed team",
        ],
        "trait": True,
        "pain_points": [
            "Endpoint security for remote devices",
            "VPN/ZTNA complexity",
            "Collaboration tool sprawl",
        ],
    },
}


# ---------------------------------------------------------------------------
# Title Priority Map & Buying-Role Mapping
# ---------------------------------------------------------------------------

class BuyingRole(Enum):
    ECONOMIC_BUYER = "economic_buyer"       # Signs the check
    TECHNICAL_BUYER = "technical_buyer"     # Evaluates technical fit
    CHAMPION = "champion"                   # Internal advocate
    INFLUENCER = "influencer"               # Shapes opinion but doesn't decide
    END_USER = "end_user"                   # Uses the service


TITLE_PRIORITY_MAP = {
    # Tier 1 - Primary decision makers (score 100)
    "Owner": {"priority": 1, "score": 100, "buying_role": BuyingRole.ECONOMIC_BUYER},
    "CEO": {"priority": 1, "score": 100, "buying_role": BuyingRole.ECONOMIC_BUYER},
    "President": {"priority": 1, "score": 100, "buying_role": BuyingRole.ECONOMIC_BUYER},
    "Founder": {"priority": 1, "score": 100, "buying_role": BuyingRole.ECONOMIC_BUYER},
    "Managing Partner": {"priority": 1, "score": 95, "buying_role": BuyingRole.ECONOMIC_BUYER},

    # Tier 2 - C-suite / VP with IT or Ops purview (score 85-95)
    "COO": {"priority": 2, "score": 95, "buying_role": BuyingRole.ECONOMIC_BUYER},
    "CFO": {"priority": 2, "score": 90, "buying_role": BuyingRole.ECONOMIC_BUYER},
    "CTO": {"priority": 2, "score": 90, "buying_role": BuyingRole.TECHNICAL_BUYER},
    "CIO": {"priority": 2, "score": 90, "buying_role": BuyingRole.TECHNICAL_BUYER},
    "CISO": {"priority": 2, "score": 85, "buying_role": BuyingRole.TECHNICAL_BUYER},
    "VP of Operations": {"priority": 2, "score": 88, "buying_role": BuyingRole.ECONOMIC_BUYER},
    "VP of IT": {"priority": 2, "score": 85, "buying_role": BuyingRole.TECHNICAL_BUYER},
    "VP of Technology": {"priority": 2, "score": 85, "buying_role": BuyingRole.TECHNICAL_BUYER},

    # Tier 3 - Directors / Heads (score 70-84)
    "Director of IT": {"priority": 3, "score": 80, "buying_role": BuyingRole.TECHNICAL_BUYER},
    "Director of Operations": {"priority": 3, "score": 78, "buying_role": BuyingRole.CHAMPION},
    "Head of IT": {"priority": 3, "score": 80, "buying_role": BuyingRole.TECHNICAL_BUYER},
    "IT Director": {"priority": 3, "score": 80, "buying_role": BuyingRole.TECHNICAL_BUYER},
    "Director of Finance": {"priority": 3, "score": 72, "buying_role": BuyingRole.INFLUENCER},
    "Controller": {"priority": 3, "score": 70, "buying_role": BuyingRole.INFLUENCER},
    "Office Manager": {"priority": 3, "score": 70, "buying_role": BuyingRole.CHAMPION},

    # Tier 4 - Managers / Leads (score 50-69)
    "IT Manager": {"priority": 4, "score": 65, "buying_role": BuyingRole.CHAMPION},
    "Systems Administrator": {"priority": 4, "score": 55, "buying_role": BuyingRole.CHAMPION},
    "Network Administrator": {"priority": 4, "score": 55, "buying_role": BuyingRole.CHAMPION},
    "Operations Manager": {"priority": 4, "score": 60, "buying_role": BuyingRole.INFLUENCER},
    "Facilities Manager": {"priority": 4, "score": 50, "buying_role": BuyingRole.INFLUENCER},
}

# Fuzzy-match patterns for title normalization
TITLE_PATTERNS = [
    # (regex_pattern, canonical_title)
    (r"(?i)\b(owner|co-owner)\b", "Owner"),
    (r"(?i)\bchief executive\b", "CEO"),
    (r"(?i)\bchief operating\b", "COO"),
    (r"(?i)\bchief financial\b", "CFO"),
    (r"(?i)\bchief technology\b", "CTO"),
    (r"(?i)\bchief information officer\b", "CIO"),
    (r"(?i)\bchief information security\b", "CISO"),
    (r"(?i)\bvp\b.*\b(it|tech)", "VP of IT"),
    (r"(?i)\bvp\b.*\bop", "VP of Operations"),
    (r"(?i)\bdirector\b.*\b(it|tech)", "Director of IT"),
    (r"(?i)\bdirector\b.*\bop", "Director of Operations"),
    (r"(?i)\b(it|tech)\s*manager\b", "IT Manager"),
    (r"(?i)\bsys\s*admin", "Systems Administrator"),
    (r"(?i)\boffice\s*manager\b", "Office Manager"),
]


# ---------------------------------------------------------------------------
# Exclusion Rules
# ---------------------------------------------------------------------------

EXCLUSION_RULES = {
    "company_size": {
        "min_employees": 3,     # Below 3 = sole proprietor / too small
        "max_employees": 200,   # Above 200 = likely has in-house IT dept
    },
    "excluded_industries": [
        "government",           # Long procurement, not a fit
        "education_k12",        # E-Rate complexity
        "big_tech",             # Not our market
        "defense_classified",   # ITAR/clearance overhead beyond scope
    ],
    "excluded_keywords": [
        "enterprise",           # Usually means 500+ employees
        "Fortune 500",
        "government contractor",  # Unless specifically CMMC-seeking
    ],
    "excluded_titles": [
        "Intern",
        "Student",
        "Consultant",           # Competing service providers
        "MSP",
        "Managed Service",
    ],
    "company_denylist": [
        # Competitors - never prospect
        "Accenture", "Deloitte", "Kforce",
        # Add specific competitors as identified
    ],
    "email_domain_denylist": [
        "gmail.com",            # Personal emails for B2B = low quality
        "yahoo.com",
        "hotmail.com",
        "outlook.com",          # Personal Outlook, not business
        "aol.com",
    ],
    "recently_contacted_days": 90,  # Don't re-prospect within 90 days
}


# ---------------------------------------------------------------------------
# Composite ICP_RULES export
# ---------------------------------------------------------------------------

ICP_RULES = {
    "size_bands": COMPANY_SIZE_BANDS,
    "industries": TARGET_INDUSTRIES,
    "title_priority_map": TITLE_PRIORITY_MAP,
    "title_patterns": TITLE_PATTERNS,
    "exclusion_rules": EXCLUSION_RULES,
    "scoring": {
        "max_score": 100,
        "qualified_threshold": 60,
        "high_priority_threshold": 80,
        "weights": {
            "company_size": 0.25,
            "industry_fit": 0.25,
            "title_score": 0.20,
            "geo_fit": 0.15,
            "engagement_signals": 0.15,
        },
    },
}
