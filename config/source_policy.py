"""
MCRcore Growth Engine - Lead Source Policy
Defines allowed lead sources, denylist rules, pending-review handling,
and risk scoring for data provenance governance.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SourceStatus(Enum):
    APPROVED = "approved"
    PENDING_REVIEW = "pending_review"
    DENIED = "denied"


class RiskLevel(Enum):
    LOW = "low"           # Trusted, verified sources
    MEDIUM = "medium"     # Generally reliable, needs validation
    HIGH = "high"         # Requires manual review before use
    BLOCKED = "blocked"   # Do not use


@dataclass
class LeadSource:
    id: str
    name: str
    category: str
    status: SourceStatus
    risk_level: RiskLevel
    data_quality_score: int      # 1-100 expected data quality
    requires_verification: bool  # Must verify email/phone before outreach
    requires_opt_in: bool        # Requires explicit consent tracking
    max_daily_pulls: Optional[int]  # Rate limit for API sources
    notes: str


# ---------------------------------------------------------------------------
# Source Allowlist
# ---------------------------------------------------------------------------

APPROVED_SOURCES: dict[str, LeadSource] = {

    "linkedin_sales_nav": LeadSource(
        id="linkedin_sales_nav",
        name="LinkedIn Sales Navigator",
        category="prospecting_platform",
        status=SourceStatus.APPROVED,
        risk_level=RiskLevel.LOW,
        data_quality_score=85,
        requires_verification=True,   # Verify email separately
        requires_opt_in=False,        # B2B legitimate interest
        max_daily_pulls=100,          # LinkedIn rate limits
        notes="Primary prospecting source. Export via Sales Nav API or manual. "
              "Always cross-reference with email verification service.",
    ),

    "apollo": LeadSource(
        id="apollo",
        name="Apollo.io",
        category="prospecting_platform",
        status=SourceStatus.APPROVED,
        risk_level=RiskLevel.LOW,
        data_quality_score=80,
        requires_verification=True,
        requires_opt_in=False,
        max_daily_pulls=500,
        notes="Bulk prospecting and enrichment. Good for company + contact discovery. "
              "Verify emails before outreach (Apollo's built-in verification is decent).",
    ),

    "zoominfo": LeadSource(
        id="zoominfo",
        name="ZoomInfo",
        category="prospecting_platform",
        status=SourceStatus.APPROVED,
        risk_level=RiskLevel.LOW,
        data_quality_score=88,
        requires_verification=False,  # ZoomInfo pre-verifies
        requires_opt_in=False,
        max_daily_pulls=250,
        notes="Highest data quality for firmographics and direct dials. "
              "Premium source — use for high-priority prospects.",
    ),

    "tallman_referrals": LeadSource(
        id="tallman_referrals",
        name="Tallman Equipment Group Referrals",
        category="referral",
        status=SourceStatus.APPROVED,
        risk_level=RiskLevel.LOW,
        data_quality_score=95,
        requires_verification=False,
        requires_opt_in=False,
        max_daily_pulls=None,  # No limit - referrals are gold
        notes="Highest-quality source. Warm introductions from Tallman's network. "
              "Always prioritize and fast-track these leads.",
    ),

    "mcrcore_inbound": LeadSource(
        id="mcrcore_inbound",
        name="mcrcore.com Inbound",
        category="inbound",
        status=SourceStatus.APPROVED,
        risk_level=RiskLevel.LOW,
        data_quality_score=90,
        requires_verification=False,  # They submitted the form
        requires_opt_in=True,         # Website form = opt-in
        max_daily_pulls=None,
        notes="Website form submissions, chat inquiries, content downloads. "
              "Highest intent — respond within 5 minutes during business hours.",
    ),

    "industry_associations": LeadSource(
        id="industry_associations",
        name="Industry Association Directories",
        category="directory",
        status=SourceStatus.APPROVED,
        risk_level=RiskLevel.MEDIUM,
        data_quality_score=70,
        requires_verification=True,
        requires_opt_in=False,
        max_daily_pulls=50,
        notes="Member directories from TCA, TMSA, NASSTRAC, NTDA, etc. "
              "Good for building targeted lists by vertical. Verify before outreach.",
    ),

    "chicagoland_chamber": LeadSource(
        id="chicagoland_chamber",
        name="Chicagoland Chamber of Commerce",
        category="directory",
        status=SourceStatus.APPROVED,
        risk_level=RiskLevel.LOW,
        data_quality_score=75,
        requires_verification=True,
        requires_opt_in=False,
        max_daily_pulls=30,
        notes="Local business directory. Good for Midwest geo-targeting. "
              "Cross-reference with firmographic data for size/industry fit.",
    ),

    "bni": LeadSource(
        id="bni",
        name="BNI (Business Network International)",
        category="referral_network",
        status=SourceStatus.APPROVED,
        risk_level=RiskLevel.LOW,
        data_quality_score=80,
        requires_verification=False,
        requires_opt_in=False,
        max_daily_pulls=None,
        notes="Referral-based leads from BNI chapter members. "
              "Warm introductions — treat as referrals, not cold outreach.",
    ),

    "cold_email_verified": LeadSource(
        id="cold_email_verified",
        name="Cold Email (Verified)",
        category="outbound",
        status=SourceStatus.APPROVED,
        risk_level=RiskLevel.MEDIUM,
        data_quality_score=65,
        requires_verification=True,   # MUST be verified before send
        requires_opt_in=False,        # B2B CAN-SPAM compliant cold email
        max_daily_pulls=None,
        notes="Cold outbound email from verified B2B addresses. "
              "Must pass email verification (ZeroBounce/NeverBounce). "
              "Must include unsubscribe. Must comply with CAN-SPAM.",
    ),
}


# ---------------------------------------------------------------------------
# Denylist Rules
# ---------------------------------------------------------------------------

DENYLIST_RULES = {
    "source_types_denied": [
        {
            "type": "scraped_unverified",
            "reason": "Unverified scraped data leads to high bounce rates and spam complaints",
            "risk_level": RiskLevel.BLOCKED,
        },
        {
            "type": "purchased_bulk_lists",
            "reason": "Bulk purchased lists have poor data quality and compliance risk",
            "risk_level": RiskLevel.BLOCKED,
        },
        {
            "type": "personal_social_media",
            "reason": "Facebook, Instagram, Twitter DMs are not appropriate B2B channels",
            "risk_level": RiskLevel.BLOCKED,
        },
        {
            "type": "consumer_data_brokers",
            "reason": "Consumer data (Spokeo, WhitePages) is not B2B appropriate",
            "risk_level": RiskLevel.BLOCKED,
        },
    ],

    "domain_denylist": [
        # Personal email providers (not valid B2B contacts)
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "aol.com", "icloud.com", "mail.com", "protonmail.com",
        # Competitor domains - never scrape or prospect
        # Add competitor domains here as identified
    ],

    "company_denylist": [
        # Direct competitors
        # Add as identified during prospecting
    ],

    "regulatory_denylist": [
        # Companies that have sent cease-and-desist or opt-out requests
        # Maintained dynamically in the database
    ],
}


# ---------------------------------------------------------------------------
# Pending Review Handling
# ---------------------------------------------------------------------------

PENDING_REVIEW_POLICY = {
    "auto_approve_conditions": [
        "Source is in APPROVED_SOURCES list",
        "Email passes verification check",
        "Company matches ICP size and industry criteria",
        "No match on any denylist",
    ],
    "requires_human_review": [
        "Source not in APPROVED_SOURCES (unknown provenance)",
        "Email verification returns 'risky' or 'unknown' status",
        "Company is in a regulated industry not in our ICP",
        "Contact has 'Do Not Contact' flag from CRM",
        "Lead score is borderline (within 5 points of threshold)",
    ],
    "review_sla_hours": 24,         # Must be reviewed within 24 hours
    "auto_reject_after_days": 7,    # If not reviewed in 7 days, auto-reject
    "reviewer_role": "growth_ops",  # Who handles pending reviews
    "notification_channel": "teams_webhook_alerts",
}


# ---------------------------------------------------------------------------
# Risk Scoring
# ---------------------------------------------------------------------------

RISK_SCORING = {
    "factors": {
        "source_risk": {
            "weight": 0.30,
            "scoring": {
                RiskLevel.LOW: 0,
                RiskLevel.MEDIUM: 30,
                RiskLevel.HIGH: 70,
                RiskLevel.BLOCKED: 100,
            },
        },
        "email_validity": {
            "weight": 0.25,
            "scoring": {
                "valid": 0,
                "catch_all": 20,      # Accept-all domains
                "risky": 50,
                "unknown": 60,
                "invalid": 100,
            },
        },
        "data_freshness": {
            "weight": 0.15,
            "scoring": {
                "under_30_days": 0,
                "30_to_90_days": 10,
                "90_to_180_days": 30,
                "over_180_days": 60,
                "unknown_age": 40,
            },
        },
        "duplicate_signals": {
            "weight": 0.15,
            "scoring": {
                "no_duplicates": 0,
                "exists_in_crm_active": 80,    # Already being worked
                "exists_in_crm_closed": 20,    # Previously closed - may re-engage
                "exists_in_pipeline": 100,     # Active deal - do not duplicate
            },
        },
        "compliance_flags": {
            "weight": 0.15,
            "scoring": {
                "no_flags": 0,
                "opted_out_past": 90,           # Previously opted out
                "do_not_contact": 100,          # Hard DNC
                "competitor_employee": 80,      # Don't prospect competitors
                "minor_company": 50,            # Under minimum size
            },
        },
    },
    "thresholds": {
        "auto_approve": 20,       # Risk score 0-20: auto-approve for outreach
        "manual_review": 50,      # Risk score 21-50: needs human review
        "auto_reject": 50,        # Risk score 51+: auto-reject
    },
}


# ---------------------------------------------------------------------------
# Composite export
# ---------------------------------------------------------------------------

SOURCE_POLICY = {
    "approved_sources": APPROVED_SOURCES,
    "denylist_rules": DENYLIST_RULES,
    "pending_review_policy": PENDING_REVIEW_POLICY,
    "risk_scoring": RISK_SCORING,
    "governance": {
        "data_retention_days": 365,          # Purge unused leads after 1 year
        "opt_out_retention": "indefinite",   # Never delete opt-out records
        "audit_log_enabled": True,           # Log all source decisions
        "gdpr_applicable": False,            # B2B North America focus
        "can_spam_compliant": True,          # All outbound must comply
    },
}
