"""
MCRcore Growth Engine - Service Catalog
All 10 MCRcore service offerings with pricing, margin bands,
commercial roles (who sells / delivers), and use cases.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PricingModel(Enum):
    PER_MONTH = "per_month"
    PER_SEAT_MONTH = "per_seat_month"
    HOURLY = "hourly"
    QUOTED = "quoted"
    PROJECT = "project"


class MarginBand(Enum):
    HIGH = "high"       # 60%+ gross margin
    MEDIUM = "medium"   # 40-60% gross margin
    LOW = "low"         # 20-40% gross margin
    VARIABLE = "variable"  # Depends on scope


@dataclass
class Service:
    id: str
    name: str
    tagline: str
    description: str
    pricing_model: PricingModel
    base_price: Optional[float]  # None = quoted
    price_label: str
    margin_band: MarginBand
    recurring: bool
    commercial_role: str         # Who owns the sale
    delivery_role: str           # Who delivers
    use_cases: list[str]
    upsell_to: list[str]         # Service IDs this naturally leads to
    ideal_size_bands: list[str]  # micro, small, mid
    keywords: list[str]          # Trigger words in prospect signals


# ---------------------------------------------------------------------------
# The 10 MCRcore Services
# ---------------------------------------------------------------------------

SERVICES: dict[str, Service] = {
    "essential_cybersecurity": Service(
        id="essential_cybersecurity",
        name="Essential Cybersecurity",
        tagline="Enterprise-grade protection at SMB prices",
        description=(
            "Foundational cybersecurity package including endpoint protection, "
            "email security, DNS filtering, and security awareness training. "
            "Designed as the minimum viable security posture for any SMB."
        ),
        pricing_model=PricingModel.PER_MONTH,
        base_price=25.00,
        price_label="$25/mo per endpoint",
        margin_band=MarginBand.HIGH,
        recurring=True,
        commercial_role="AE / Automated sequence",
        delivery_role="SOC / Managed Security",
        use_cases=[
            "Company with no current endpoint protection",
            "Post-breach remediation baseline",
            "Compliance checkbox (cyber insurance requirement)",
            "Entry point before full managed services",
        ],
        upsell_to=["proactive_monitoring", "total_plan", "technical_audit"],
        ideal_size_bands=["micro", "small", "mid"],
        keywords=["cybersecurity", "ransomware", "breach", "endpoint", "antivirus",
                  "cyber insurance", "security training", "phishing"],
    ),

    "proactive_monitoring": Service(
        id="proactive_monitoring",
        name="Proactive Network Monitoring",
        tagline="See problems before your team does",
        description=(
            "24/7 network and infrastructure monitoring with alerting, "
            "patch management, and proactive remediation. Covers servers, "
            "firewalls, switches, and critical endpoints."
        ),
        pricing_model=PricingModel.PER_MONTH,
        base_price=100.00,
        price_label="$100/mo per site",
        margin_band=MarginBand.HIGH,
        recurring=True,
        commercial_role="AE / Fractional CIO recommendation",
        delivery_role="NOC / Remote Support",
        use_cases=[
            "Company experiencing frequent unplanned downtime",
            "Multi-site needing centralized visibility",
            "Augmenting a lone IT person with 24/7 coverage",
            "Pre-requisite for SLA-backed support",
        ],
        upsell_to=["total_plan", "virtual_servers"],
        ideal_size_bands=["micro", "small", "mid"],
        keywords=["downtime", "monitoring", "network issues", "patch management",
                  "server alerts", "outage", "slow network"],
    ),

    "total_plan": Service(
        id="total_plan",
        name="Total Plan (Managed IT)",
        tagline="Your complete IT department — without the overhead",
        description=(
            "Fully managed IT services: helpdesk, on-site support, proactive monitoring, "
            "cybersecurity, vendor management, strategic planning (vCIO), and procurement. "
            "Flat per-seat pricing with predictable monthly costs."
        ),
        pricing_model=PricingModel.PER_SEAT_MONTH,
        base_price=150.00,
        price_label="$150/seat/mo",
        margin_band=MarginBand.MEDIUM,
        recurring=True,
        commercial_role="AE + Fractional CIO (strategic sale)",
        delivery_role="Full stack: NOC + SOC + Field + vCIO",
        use_cases=[
            "Company with no IT department wanting full outsource",
            "Replacing a departing IT manager",
            "Consolidating multiple IT vendors into one partner",
            "Scaling company needing IT that grows with them",
        ],
        upsell_to=["fractional_cio", "it_process_automation", "voip"],
        ideal_size_bands=["small", "mid"],
        keywords=["managed IT", "outsourced IT", "MSP", "IT department",
                  "helpdesk", "IT support", "per seat"],
    ),

    "on_demand_break_fix": Service(
        id="on_demand_break_fix",
        name="On-Demand / Break & Fix",
        tagline="Expert help when you need it — no contract required",
        description=(
            "Hourly IT support for companies not ready for a managed plan. "
            "Covers troubleshooting, repairs, moves/adds/changes, and project work. "
            "Often serves as the entry point to a managed relationship."
        ),
        pricing_model=PricingModel.HOURLY,
        base_price=None,  # TBD - rate card varies
        price_label="Hourly (rate TBD)",
        margin_band=MarginBand.VARIABLE,
        recurring=False,
        commercial_role="AE / Inbound triage",
        delivery_role="Field Tech / Remote Support",
        use_cases=[
            "Urgent issue with no current IT provider",
            "One-time project (office move, setup)",
            "Company evaluating MCRcore before committing to managed plan",
            "Overflow support for internal IT team",
        ],
        upsell_to=["essential_cybersecurity", "proactive_monitoring", "total_plan"],
        ideal_size_bands=["micro", "small"],
        keywords=["break fix", "IT help", "emergency", "troubleshooting",
                  "computer repair", "network down", "server crash"],
    ),

    "virtual_servers": Service(
        id="virtual_servers",
        name="Virtual Servers (Cloud Hosting)",
        tagline="Enterprise infrastructure without the server closet",
        description=(
            "Hosted virtual server environments with managed backups, "
            "disaster recovery, and 24/7 monitoring. Replaces aging on-prem "
            "hardware with scalable cloud infrastructure."
        ),
        pricing_model=PricingModel.QUOTED,
        base_price=None,
        price_label="Custom quoted",
        margin_band=MarginBand.MEDIUM,
        recurring=True,
        commercial_role="AE + Solutions Architect",
        delivery_role="Cloud Engineering / NOC",
        use_cases=[
            "End-of-life server hardware needing replacement",
            "Company wanting to eliminate on-prem infrastructure",
            "Disaster recovery / business continuity planning",
            "ERP hosting (Epicor P21, McLeod in the cloud)",
        ],
        upsell_to=["proactive_monitoring", "total_plan"],
        ideal_size_bands=["small", "mid"],
        keywords=["server", "cloud", "hosting", "virtualization", "disaster recovery",
                  "backup", "migration", "end of life", "hardware refresh"],
    ),

    "fractional_cio": Service(
        id="fractional_cio",
        name="Fractional CIO",
        tagline="C-level IT strategy without the C-level salary",
        description=(
            "Part-time Chief Information Officer providing strategic IT planning, "
            "budgeting, vendor management, and technology roadmapping. Attends "
            "leadership meetings, aligns IT with business goals."
        ),
        pricing_model=PricingModel.QUOTED,
        base_price=None,
        price_label="Custom quoted (retainer)",
        margin_band=MarginBand.HIGH,
        recurring=True,
        commercial_role="Founder / Senior AE (relationship sale)",
        delivery_role="vCIO / Fractional CIO",
        use_cases=[
            "Company making major technology decisions without IT leadership",
            "M&A integration requiring IT due diligence",
            "Board or investors asking for IT strategy/risk assessment",
            "Scaling company needing IT roadmap for next 2-3 years",
        ],
        upsell_to=["total_plan", "it_process_automation", "technical_audit"],
        ideal_size_bands=["small", "mid"],
        keywords=["CIO", "IT strategy", "IT budget", "technology roadmap",
                  "IT leadership", "digital transformation", "IT planning"],
    ),

    "it_process_automation": Service(
        id="it_process_automation",
        name="IT Process Automation",
        tagline="Automate the repetitive, focus on the strategic",
        description=(
            "Custom automation of IT and business processes: user provisioning/deprovisioning, "
            "reporting, data flows between systems, approval workflows. "
            "Reduces manual effort and human error."
        ),
        pricing_model=PricingModel.QUOTED,
        base_price=None,
        price_label="Custom quoted (project + retainer)",
        margin_band=MarginBand.HIGH,
        recurring=True,  # Typically becomes a retainer after project
        commercial_role="Fractional CIO / Solutions Architect",
        delivery_role="Automation Engineer / Integration Specialist",
        use_cases=[
            "Manual employee onboarding/offboarding taking hours",
            "Data entry between disconnected systems",
            "Compliance reporting requiring manual assembly",
            "ERP-to-CRM or ERP-to-eCommerce data sync",
        ],
        upsell_to=["fractional_cio", "total_plan"],
        ideal_size_bands=["small", "mid"],
        keywords=["automation", "workflow", "integration", "API", "provisioning",
                  "onboarding", "data sync", "manual process", "RPA"],
    ),

    "voip": Service(
        id="voip",
        name="VOIP Phone Systems",
        tagline="Modern business communications, fully managed",
        description=(
            "Cloud-based phone systems with auto-attendant, call routing, "
            "voicemail-to-email, mobile app, and integration with CRM/ERP. "
            "Replaces legacy PBX with scalable UCaaS."
        ),
        pricing_model=PricingModel.QUOTED,
        base_price=None,
        price_label="Custom quoted per seat",
        margin_band=MarginBand.MEDIUM,
        recurring=True,
        commercial_role="AE (often bundled with Total Plan)",
        delivery_role="Voice Engineer / NOC",
        use_cases=[
            "Legacy PBX end-of-life or expensive maintenance",
            "Multi-site needing unified phone system",
            "Remote workers needing business phone on mobile",
            "Company wanting CRM integration with phone system",
        ],
        upsell_to=["total_plan", "wfh_implementation"],
        ideal_size_bands=["micro", "small", "mid"],
        keywords=["phone system", "VOIP", "PBX", "telecom", "call routing",
                  "auto attendant", "UCaaS", "Teams calling"],
    ),

    "wfh_implementation": Service(
        id="wfh_implementation",
        name="Work From Home Implementation",
        tagline="Secure, productive remote work — done right",
        description=(
            "End-to-end remote/hybrid work enablement: VPN or ZTNA setup, "
            "endpoint hardening, collaboration tools deployment, remote "
            "monitoring, and security policies for distributed teams."
        ),
        pricing_model=PricingModel.QUOTED,
        base_price=None,
        price_label="Custom quoted (project)",
        margin_band=MarginBand.MEDIUM,
        recurring=False,  # Project, but leads to recurring monitoring
        commercial_role="AE / Fractional CIO",
        delivery_role="Solutions Architect / Field Tech",
        use_cases=[
            "Company shifting to hybrid model post-COVID",
            "Security concerns about remote employee devices",
            "Deploying collaboration tools (Teams, Slack) company-wide",
            "Setting up secure remote access to ERP/LOB applications",
        ],
        upsell_to=["essential_cybersecurity", "proactive_monitoring", "voip"],
        ideal_size_bands=["small", "mid"],
        keywords=["work from home", "WFH", "remote work", "hybrid", "VPN",
                  "zero trust", "remote access", "collaboration"],
    ),

    "technical_audit": Service(
        id="technical_audit",
        name="Technical Audit",
        tagline="Know exactly where you stand before making IT decisions",
        description=(
            "Comprehensive assessment of IT infrastructure, security posture, "
            "and operational maturity. Delivers a scored report with prioritized "
            "recommendations. Often the first engagement with MCRcore."
        ),
        pricing_model=PricingModel.PROJECT,
        base_price=None,  # Varies by scope; sometimes offered free as lead magnet
        price_label="Scoped (often complimentary for qualified prospects)",
        margin_band=MarginBand.VARIABLE,
        recurring=False,
        commercial_role="AE / Fractional CIO (audit-first engagement model)",
        delivery_role="Solutions Architect / Senior Engineer",
        use_cases=[
            "Company unsure of their current IT security posture",
            "New leadership wanting baseline assessment",
            "Pre-M&A IT due diligence",
            "Cyber insurance application requiring documentation",
            "Audit-first: MCRcore's primary door-opener engagement",
        ],
        upsell_to=["essential_cybersecurity", "total_plan", "fractional_cio"],
        ideal_size_bands=["micro", "small", "mid"],
        keywords=["audit", "assessment", "IT review", "security assessment",
                  "gap analysis", "due diligence", "compliance audit"],
    ),
}


# ---------------------------------------------------------------------------
# Margin Bands (for financial modeling / agent scoring)
# ---------------------------------------------------------------------------

MARGIN_BANDS = {
    MarginBand.HIGH: {
        "label": "High Margin (60%+)",
        "min_gross_margin_pct": 60,
        "priority_score": 100,
        "notes": "Prioritize in outbound. Software-heavy, low delivery cost.",
    },
    MarginBand.MEDIUM: {
        "label": "Medium Margin (40-60%)",
        "min_gross_margin_pct": 40,
        "priority_score": 75,
        "notes": "Core managed services. Good LTV with retention.",
    },
    MarginBand.LOW: {
        "label": "Low Margin (20-40%)",
        "min_gross_margin_pct": 20,
        "priority_score": 50,
        "notes": "Hardware-heavy or labor-intensive. Acceptable as part of bundle.",
    },
    MarginBand.VARIABLE: {
        "label": "Variable Margin",
        "min_gross_margin_pct": 0,
        "priority_score": 60,
        "notes": "Scope-dependent. Ensure SOW pricing covers costs.",
    },
}


# ---------------------------------------------------------------------------
# Composite export
# ---------------------------------------------------------------------------

SERVICE_CATALOG = {
    "services": SERVICES,
    "margin_bands": MARGIN_BANDS,
    "lead_magnet_service": "technical_audit",
    "entry_point_services": ["essential_cybersecurity", "on_demand_break_fix", "technical_audit"],
    "flagship_service": "total_plan",
    "highest_margin_services": ["essential_cybersecurity", "fractional_cio", "it_process_automation"],
}
