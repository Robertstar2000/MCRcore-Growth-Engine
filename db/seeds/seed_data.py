"""
MCRcore Growth Engine - Seed Data

Populates the database with:
  1. Approved source allowlist
  2. Service packages (stored as Sources of type 'config')
  3. Differentiators (stored as audit log config entries)
  4. ICP (Ideal Customer Profile) configuration

Usage:
    python -m db.seeds.seed_data
"""

import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from db.database import get_session, init_db
from db.repositories import (
    AuditRepository,
    SourceRepository,
)
from db.models import Source, AuditEvent

# ===================================================================
# 1. Source Allowlist
# ===================================================================
SOURCE_ALLOWLIST = [
    {
        "source_name": "linkedin_navigator",
        "source_type": "scraper",
        "approved_flag": True,
        "risk_level": "low",
        "provenance_ref": "LinkedIn Sales Navigator export",
    },
    {
        "source_name": "apollo_io",
        "source_type": "data_vendor",
        "approved_flag": True,
        "risk_level": "low",
        "provenance_ref": "Apollo.io enrichment API",
    },
    {
        "source_name": "zoominfo",
        "source_type": "data_vendor",
        "approved_flag": True,
        "risk_level": "low",
        "provenance_ref": "ZoomInfo data export",
    },
    {
        "source_name": "website_scraper",
        "source_type": "scraper",
        "approved_flag": True,
        "risk_level": "medium",
        "provenance_ref": "Custom web scraper – public company pages",
    },
    {
        "source_name": "referral_internal",
        "source_type": "referral",
        "approved_flag": True,
        "risk_level": "low",
        "provenance_ref": "Internal team referral",
    },
    {
        "source_name": "event_tradeshow",
        "source_type": "event",
        "approved_flag": True,
        "risk_level": "low",
        "provenance_ref": "Trade show / conference badge scan",
    },
    {
        "source_name": "purchased_list_generic",
        "source_type": "purchased",
        "approved_flag": False,
        "risk_level": "high",
        "provenance_ref": "Third-party purchased list – requires compliance review",
    },
    {
        "source_name": "inbound_website",
        "source_type": "inbound",
        "approved_flag": True,
        "risk_level": "low",
        "provenance_ref": "Website contact form / chatbot",
    },
    {
        "source_name": "partner_referral",
        "source_type": "referral",
        "approved_flag": True,
        "risk_level": "low",
        "provenance_ref": "Partner / vendor referral program",
    },
]

# ===================================================================
# 2. Service Packages (MCR offerings)
# ===================================================================
SERVICE_PACKAGES = [
    {
        "name": "Managed IT Foundation",
        "description": "Core managed services: monitoring, helpdesk, patch management, endpoint protection.",
        "entry_cta": "Free IT Health Check",
        "target_employee_band": "20-200",
        "margin_band": "high",
    },
    {
        "name": "Cloud Migration & Optimization",
        "description": "Azure/M365 migration, cloud cost optimization, hybrid infrastructure.",
        "entry_cta": "Cloud Readiness Assessment",
        "target_employee_band": "50-500",
        "margin_band": "medium-high",
    },
    {
        "name": "Cybersecurity & Compliance",
        "description": "CMMC/NIST compliance, SOC monitoring, vulnerability management, incident response.",
        "entry_cta": "Free Security Gap Analysis",
        "target_employee_band": "50-1000",
        "margin_band": "high",
    },
    {
        "name": "ERP & Business Applications",
        "description": "Epicor consulting, ERP optimization, integration services, custom development.",
        "entry_cta": "ERP Performance Review",
        "target_employee_band": "50-500",
        "margin_band": "medium-high",
    },
    {
        "name": "VoIP & Unified Communications",
        "description": "Teams Phone, VoIP migration, contact center modernization.",
        "entry_cta": "Communications Cost Audit",
        "target_employee_band": "20-500",
        "margin_band": "medium",
    },
    {
        "name": "Backup & Disaster Recovery",
        "description": "Datto/Veeam BDR, business continuity planning, DR testing.",
        "entry_cta": "DR Readiness Assessment",
        "target_employee_band": "20-500",
        "margin_band": "high",
    },
    {
        "name": "Strategic IT Consulting (vCIO)",
        "description": "Virtual CIO services, IT roadmapping, budgeting, vendor management.",
        "entry_cta": "Complimentary IT Strategy Session",
        "target_employee_band": "50-1000",
        "margin_band": "high",
    },
    {
        "name": "Logistics & TMS Integration",
        "description": "McLeod/DAT integration, logistics IT infrastructure, TMS support.",
        "entry_cta": "Logistics IT Assessment",
        "target_employee_band": "50-500",
        "margin_band": "medium-high",
    },
]

# ===================================================================
# 3. MCR Differentiators
# ===================================================================
DIFFERENTIATORS = [
    "Deep Epicor ERP expertise – certified consultants on staff",
    "Manufacturing & distribution vertical specialization",
    "Logistics / trucking IT infrastructure experience (McLeod, DAT, KeyPoint)",
    "CMMC / NIST compliance readiness for defense supply chain",
    "24x7 US-based NOC and SOC",
    "Proactive vCIO strategic planning included in managed contracts",
    "Single-vendor IT stack: managed services + ERP + security + cloud",
    "Rapid onboarding: average 14-day full managed services transition",
    "Insurance & financial services vertical compliance experience",
]

# ===================================================================
# 4. ICP Configuration (Ideal Customer Profile)
# ===================================================================
ICP_CONFIG = {
    "target_industries": [
        "Manufacturing",
        "Distribution",
        "Logistics & Transportation",
        "Insurance",
        "Financial Services",
        "Construction",
        "Professional Services",
    ],
    "target_employee_bands": ["20-50", "50-200", "200-500", "500-1000"],
    "target_geographies": [
        "United States",
        "US - Midwest",
        "US - Southeast",
        "US - Northeast",
        "US - Southwest",
        "US - West Coast",
    ],
    "priority_signals": [
        "epicor_usage",
        "mcleod_usage",
        "dat_keypoint_usage",
        "legacy_erp_migration",
        "compliance_requirements",
        "infrastructure_aging",
        "rapid_growth_scaling",
        "m_and_a_activity",
        "remote_workforce_expansion",
    ],
    "disqualifiers": [
        "employee_count_below_15",
        "already_has_msp",
        "government_entity",
        "non_us_hq",
    ],
    "scoring_weights": {
        "fit_score_weight": 0.30,
        "need_score_weight": 0.35,
        "engagement_score_weight": 0.20,
        "package_fit_score_weight": 0.15,
    },
    "tier_thresholds": {
        "A": 0.80,
        "B": 0.60,
        "C": 0.40,
        "D": 0.0,
    },
}


# ===================================================================
# Seed runner
# ===================================================================
def seed_sources(session) -> int:
    """Insert approved source records. Returns count of new records."""
    repo = SourceRepository(session)
    created = 0
    for src in SOURCE_ALLOWLIST:
        existing = repo.find_by_name(src["source_name"])
        if existing is None:
            repo.create(**src)
            created += 1
    return created


def seed_config(session) -> int:
    """
    Store service packages, differentiators, and ICP as AuditEvent
    config entries (entity_type='config') so they are versioned.
    Returns count of config entries written.
    """
    audit = AuditRepository(session)
    written = 0

    # Service packages
    audit.log(
        actor="seed_script",
        entity_type="config",
        entity_id="service_packages",
        action="seed",
        after_json=json.dumps(SERVICE_PACKAGES, indent=2),
    )
    written += 1

    # Differentiators
    audit.log(
        actor="seed_script",
        entity_type="config",
        entity_id="differentiators",
        action="seed",
        after_json=json.dumps(DIFFERENTIATORS, indent=2),
    )
    written += 1

    # ICP config
    audit.log(
        actor="seed_script",
        entity_type="config",
        entity_id="icp_config",
        action="seed",
        after_json=json.dumps(ICP_CONFIG, indent=2),
    )
    written += 1

    return written


def run_seed() -> None:
    """Execute all seed operations."""
    print("[seed] Ensuring tables exist …")
    init_db()

    with get_session() as session:
        src_count = seed_sources(session)
        print(f"[seed] Sources created: {src_count} (of {len(SOURCE_ALLOWLIST)} in allowlist)")

        cfg_count = seed_config(session)
        print(f"[seed] Config entries written: {cfg_count}")

    print("[seed] Done.")


if __name__ == "__main__":
    run_seed()
