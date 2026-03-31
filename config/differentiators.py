"""
MCRcore Growth Engine - Competitive Differentiators
8 differentiator blocks used by content-generation and outreach agents
to craft compelling, specific messaging.
"""

from dataclasses import dataclass, field


@dataclass
class Differentiator:
    id: str
    headline: str
    summary: str
    proof_points: list[str]
    messaging_hooks: list[str]
    best_for_industries: list[str]   # Keys from icp_rules.TARGET_INDUSTRIES
    best_for_services: list[str]     # Keys from service_catalog.SERVICES
    objection_it_handles: str


# ---------------------------------------------------------------------------
# The 8 MCRcore Differentiators
# ---------------------------------------------------------------------------

DIFFERENTIATOR_BLOCKS: dict[str, Differentiator] = {

    "deep_erp_expertise": Differentiator(
        id="deep_erp_expertise",
        headline="Deep ERP Expertise Your Current IT Provider Doesn't Have",
        summary=(
            "MCRcore has hands-on operational experience with the ERP systems "
            "that manufacturers, distributors, and logistics companies actually run. "
            "Not just generic IT support — real P21, McLeod, DAT, and Point of Rental knowledge."
        ),
        proof_points=[
            "Epicor Prophet 21 (P21): Server hosting, performance tuning, integration support",
            "McLeod Software: LoadMaster and PowerBroker environment management",
            "DAT Keypoint: Load-board integration, connectivity, and uptime",
            "Point of Rental: Hosting, backup, and multi-location deployment",
            "Team members with years of direct ERP administration experience",
        ],
        messaging_hooks=[
            "Your MSP says they 'support' P21 — but have they ever tuned a P21 SQL instance?",
            "When DAT goes down, your IT guy Googles it. We've already fixed it.",
            "We speak ERP fluently — not just 'we can remote into your server.'",
            "The IT partner who actually understands your business-critical systems.",
        ],
        best_for_industries=["manufacturing", "supply_chain", "freight_logistics"],
        best_for_services=["total_plan", "virtual_servers", "fractional_cio"],
        objection_it_handles="Our current IT provider handles our ERP fine.",
    ),

    "not_generic_msp": Differentiator(
        id="not_generic_msp",
        headline="We're Not a Generic MSP — We're a Business Technology Partner",
        summary=(
            "Most MSPs sell tickets and seats. MCRcore starts with your business goals "
            "and works backward to the technology. We don't upsell unnecessary tools — "
            "we solve the problems that keep you from growing."
        ),
        proof_points=[
            "Every engagement starts with understanding business objectives, not an RMM install",
            "Fractional CIO attends your leadership meetings — not just your server room",
            "Technology recommendations tied to ROI and business outcomes",
            "No long-term lock-in contracts — we earn your business monthly",
        ],
        messaging_hooks=[
            "Tired of an MSP that only calls when your bill is due?",
            "We don't sell seats. We solve business problems with technology.",
            "Your MSP manages your network. We manage your IT strategy.",
            "The difference between an IT vendor and an IT partner.",
        ],
        best_for_industries=["scaling_smb", "manufacturing", "insurance"],
        best_for_services=["total_plan", "fractional_cio", "technical_audit"],
        objection_it_handles="All MSPs are the same.",
    ),

    "dual_delivery_model": Differentiator(
        id="dual_delivery_model",
        headline="On-Site + Remote: The Dual Delivery Model",
        summary=(
            "MCRcore combines local, on-site presence in the Midwest and Northern Florida "
            "with a full remote support capability covering all of North America. "
            "You get boots on the ground when needed and instant remote help 24/7."
        ),
        proof_points=[
            "Local field technicians in Chicagoland and Northern Florida markets",
            "Remote NOC/SOC staffed 24/7 for monitoring, alerting, and remediation",
            "Same-day on-site response for critical issues in core markets",
            "Remote-first services available nationwide (cybersecurity, monitoring, vCIO)",
        ],
        messaging_hooks=[
            "Remote support for speed. On-site support when it matters.",
            "National reach, local touch.",
            "Your server's down at 2 AM — our NOC is already on it.",
            "We show up. In person. When you need us.",
        ],
        best_for_industries=["multi_site", "manufacturing", "supply_chain"],
        best_for_services=["total_plan", "proactive_monitoring", "on_demand_break_fix"],
        objection_it_handles="We need someone local / We need someone who can be on-site.",
    ),

    "fractional_cio_access": Differentiator(
        id="fractional_cio_access",
        headline="C-Level IT Leadership Without the $200K Salary",
        summary=(
            "Every MCRcore managed client gets access to Fractional CIO services. "
            "Strategic IT planning, budgeting, vendor negotiation, and technology "
            "roadmapping — the kind of leadership that SMBs can't otherwise afford."
        ),
        proof_points=[
            "Dedicated vCIO assigned to every Total Plan client",
            "Quarterly business reviews with IT scorecards and roadmaps",
            "Budget planning and capital vs. operational expense guidance",
            "Vendor evaluation and negotiation on the client's behalf",
            "Board-ready IT reports and risk assessments",
        ],
        messaging_hooks=[
            "You have a CFO for your finances. Why not a CIO for your technology?",
            "Strategic IT leadership for the cost of a few helpdesk tickets.",
            "Stop making six-figure technology decisions without a technology advisor.",
            "The IT strategy your competitors' CIO is giving them — now available to you.",
        ],
        best_for_industries=["scaling_smb", "manufacturing", "insurance"],
        best_for_services=["fractional_cio", "total_plan", "it_process_automation"],
        objection_it_handles="We can't afford a CIO / We don't need full-time IT leadership.",
    ),

    "business_first_founders": Differentiator(
        id="business_first_founders",
        headline="Founded by Business Operators, Not Just Technologists",
        summary=(
            "MCRcore's leadership team brings 20+ years of experience running businesses, "
            "not just managing networks. We understand P&L, operations, growth challenges, "
            "and what it means to bet your company on technology decisions."
        ),
        proof_points=[
            "Founders with 20+ years in business operations and technology",
            "Direct experience scaling companies from startup to mid-market",
            "Background in manufacturing, logistics, and professional services",
            "We've sat in your chair — we know what keeps business owners up at night",
        ],
        messaging_hooks=[
            "Built by people who've run businesses — not just servers.",
            "We understand your P&L, not just your IP addresses.",
            "20+ years of business experience backing every IT recommendation.",
            "We've been the frustrated business owner calling IT support. Never again.",
        ],
        best_for_industries=["scaling_smb", "manufacturing", "freight_logistics"],
        best_for_services=["fractional_cio", "total_plan", "technical_audit"],
        objection_it_handles="You don't understand our business / industry.",
    ),

    "24_7_monitoring": Differentiator(
        id="24_7_monitoring",
        headline="24/7 Monitoring — Because Threats Don't Wait for Business Hours",
        summary=(
            "MCRcore's NOC and SOC operate around the clock. Real-time monitoring, "
            "automated alerting, and human-verified response — not just a dashboard "
            "someone checks Monday morning."
        ),
        proof_points=[
            "24/7/365 Network Operations Center (NOC) monitoring",
            "24/7/365 Security Operations Center (SOC) threat detection",
            "Automated remediation for common issues (patch, restart, failover)",
            "Human escalation within 15 minutes for critical alerts",
            "Monthly monitoring reports with trend analysis",
        ],
        messaging_hooks=[
            "Your firewall logged 10,000 events last night. Who reviewed them?",
            "Ransomware doesn't attack at 2 PM on a Tuesday.",
            "We're watching your network while you're sleeping.",
            "The peace of mind of enterprise-grade monitoring at SMB pricing.",
        ],
        best_for_industries=["manufacturing", "supply_chain", "compliance_sensitive"],
        best_for_services=["proactive_monitoring", "essential_cybersecurity", "total_plan"],
        objection_it_handles="We've never had a security incident / Our network is fine.",
    ),

    "audit_first_engagement": Differentiator(
        id="audit_first_engagement",
        headline="We Don't Sell First — We Audit First",
        summary=(
            "MCRcore leads with a Technical Audit, not a sales pitch. We assess your "
            "current IT environment, identify risks and gaps, and deliver a scored "
            "report with prioritized recommendations — before asking for a dime."
        ),
        proof_points=[
            "Comprehensive Technical Audit covering infrastructure, security, and operations",
            "Scored report with Red/Yellow/Green ratings by category",
            "Prioritized recommendation roadmap (quick wins + strategic initiatives)",
            "No obligation — the audit has standalone value regardless of next steps",
            "Often uncovers risks the current provider missed or ignored",
        ],
        messaging_hooks=[
            "Don't take our word for it — let the audit speak for itself.",
            "What would a 50-point IT inspection reveal about your business?",
            "Your current IT provider has never shown you this report.",
            "We earn your trust with transparency, not a sales pitch.",
        ],
        best_for_industries=["scaling_smb", "compliance_sensitive", "insurance"],
        best_for_services=["technical_audit", "total_plan", "essential_cybersecurity"],
        objection_it_handles="We're happy with our current provider / We don't need to change.",
    ),

    "tallman_backing": Differentiator(
        id="tallman_backing",
        headline="Backed by Tallman Equipment Group — Built on Real Business Foundations",
        summary=(
            "MCRcore is backed by Tallman Equipment Group, bringing institutional "
            "credibility, operational infrastructure, and a proven track record in "
            "running complex multi-site businesses. This isn't a two-person garage MSP."
        ),
        proof_points=[
            "Tallman Equipment Group: established, multi-site business operation",
            "Financial stability and investment backing for long-term commitments",
            "Real-world testing ground for every solution MCRcore deploys",
            "Operational maturity from running enterprise-grade infrastructure internally",
            "Referral network within Tallman's business ecosystem",
        ],
        messaging_hooks=[
            "Backed by a real business, not just venture capital.",
            "Every solution we recommend — we've deployed it in our own operations first.",
            "The stability of an established group. The agility of a focused IT partner.",
            "We don't just consult — we operate the same infrastructure we manage for you.",
        ],
        best_for_industries=["manufacturing", "supply_chain", "scaling_smb"],
        best_for_services=["total_plan", "virtual_servers", "proactive_monitoring"],
        objection_it_handles="You're too small / Are you going to be around in 5 years?",
    ),
}


# ---------------------------------------------------------------------------
# Composite export
# ---------------------------------------------------------------------------

DIFFERENTIATORS = {
    "blocks": DIFFERENTIATOR_BLOCKS,
    "count": len(DIFFERENTIATOR_BLOCKS),
    "primary_door_opener": "audit_first_engagement",
    "strongest_for_manufacturing": ["deep_erp_expertise", "24_7_monitoring", "dual_delivery_model"],
    "strongest_for_logistics": ["deep_erp_expertise", "24_7_monitoring", "business_first_founders"],
    "strongest_against_incumbent_msp": ["not_generic_msp", "audit_first_engagement", "fractional_cio_access"],
}
