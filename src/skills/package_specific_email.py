"""
MCRcore Growth Engine - Package-Specific Email Skill

Email templates for each of the 10 MCRcore service packages.
Each template includes:
  - Subject line variants
  - Opener
  - Value proposition
  - Differentiator slot (filled by agent at generation time)
  - CTA
  - Footer (compliance)
  - Title-aware variations (CEO, Ops, CFO, IT Mgr)

All templates use Jinja2 {{ placeholders }} for personalization.
The OutreachPersonalizationAgent selects and fills these at generation time.
"""

from typing import Dict, List, Optional

from src.templates.message_blocks import (
    PACKAGE_BLOCKS,
    TITLE_BLOCKS,
    COMPLIANCE_FOOTER,
)


# ===================================================================
# Master Email Structure (applies to all packages)
# ===================================================================

PACKAGE_EMAIL_STRUCTURE = (
    "{{ subject_line }}\n\n"
    "{{ first_name }},\n\n"
    "{{ opener }}\n\n"
    "{{ value_prop }}\n\n"
    "{{ differentiator_block }}\n\n"
    "{{ cta }}\n\n"
    "Best,\n"
    "{{ sender_name }}\n"
    "{{ sender_title }}, MCRcore\n"
    "{{ compliance_footer }}"
)


# ===================================================================
# Package-Specific Email Templates
# ===================================================================

PACKAGE_EMAIL_TEMPLATES: Dict[str, Dict] = {

    "essential_cybersecurity": {
        "subject_lines": [
            "{{ first_name }}, how exposed is {{ company_name }} right now?",
            "The cybersecurity baseline every {{ industry }} company needs",
            "{{ company_name }} — what's between your team and a breach?",
        ],
        "openers": {
            "ceo_owner": (
                "{{ first_name }}, a breach at {{ company_name }} wouldn't just "
                "be an IT problem — it would be a business crisis. The reputational "
                "and financial cost of a single incident can dwarf years of "
                "prevention investment."
            ),
            "operations": (
                "{{ first_name }}, when a ransomware attack locks your team out "
                "of their systems, operations don't just slow down — they stop. "
                "And the clock starts running on every missed shipment, order, "
                "and deadline."
            ),
            "cfo_controller": (
                "{{ first_name }}, the average cost of a data breach for a "
                "company {{ company_name }}'s size is well into six figures — "
                "before you count the operational disruption. The prevention "
                "math is compelling."
            ),
            "it_manager": (
                "{{ first_name }}, you know the gaps in {{ company_name }}'s "
                "security stack better than anyone. The question is whether "
                "you have the tools and coverage to close them without burning "
                "every hour of your week."
            ),
            "_default": (
                "{{ first_name }}, cybersecurity isn't optional anymore — it's "
                "the foundation everything else at {{ company_name }} depends on."
            ),
        },
    },

    "proactive_monitoring": {
        "subject_lines": [
            "{{ first_name }}, what happened on {{ company_name }}'s network last night?",
            "Seeing problems before your team does at {{ company_name }}",
            "{{ company_name }} — are you monitoring or just hoping?",
        ],
        "openers": {
            "ceo_owner": (
                "{{ first_name }}, you shouldn't find out about IT problems "
                "from frustrated employees walking into your office. With "
                "24/7 monitoring, you know about issues before anyone else does."
            ),
            "operations": (
                "{{ first_name }}, every unplanned outage at {{ company_name }} "
                "has a downstream cost — missed deadlines, idle workers, "
                "frustrated customers. Proactive monitoring is how you break "
                "that cycle."
            ),
            "cfo_controller": (
                "{{ first_name }}, the cost of 24/7 network monitoring is "
                "a fraction of the cost of one unplanned outage. It's the "
                "simplest risk-reduction investment on the table."
            ),
            "it_manager": (
                "{{ first_name }}, monitoring doesn't replace you — it extends "
                "you. Our NOC watches at 2 AM so you don't have to. And you "
                "get a dashboard, not just alerts."
            ),
            "_default": (
                "{{ first_name }}, the difference between monitoring and hoping "
                "is the difference between catching a $200 fix and dealing with "
                "a $20,000 outage."
            ),
        },
    },

    "total_plan": {
        "subject_lines": [
            "{{ first_name }}, what if {{ company_name }} had a complete IT department — without building one?",
            "The Total Plan: managed IT that actually manages everything",
            "{{ company_name }} — flat-rate IT that scales with you",
        ],
        "openers": {
            "ceo_owner": (
                "{{ first_name }}, building an IT department from scratch costs "
                "$400K+ per year when you add salary, benefits, tools, and "
                "training. The Total Plan gives you the same coverage at a "
                "fraction of that cost."
            ),
            "operations": (
                "{{ first_name }}, having one partner who knows {{ company_name }}'s "
                "systems inside and out means fewer handoffs, faster resolution, "
                "and someone who actually understands your operation."
            ),
            "cfo_controller": (
                "{{ first_name }}, the Total Plan converts IT from an unpredictable "
                "expense into a flat per-seat monthly cost. No surprise invoices. "
                "No scope creep charges. Just predictable IT."
            ),
            "it_manager": (
                "{{ first_name }}, the Total Plan is co-managed — you stay in "
                "the driver's seat on strategy while we handle helpdesk, "
                "monitoring, security, and vendor management. It's your team, "
                "plus ours."
            ),
            "_default": (
                "{{ first_name }}, the Total Plan gives {{ company_name }} a "
                "complete IT department — helpdesk, monitoring, security, strategy "
                "— without the overhead of building one."
            ),
        },
    },

    "on_demand_break_fix": {
        "subject_lines": [
            "{{ first_name }}, need IT help without a contract?",
            "{{ company_name }} — expert IT support, one issue at a time",
            "No contract required: just good IT help when you need it",
        ],
        "openers": {
            "ceo_owner": (
                "{{ first_name }}, not every company is ready for a full managed "
                "IT plan — and that's okay. On-Demand gives you access to "
                "expert support for the issues that matter, with zero commitment."
            ),
            "operations": (
                "{{ first_name }}, when something breaks at {{ company_name }} "
                "and your usual person can't fix it, you need someone good to "
                "call. That's exactly what On-Demand is for."
            ),
            "cfo_controller": (
                "{{ first_name }}, On-Demand IT support means {{ company_name }} "
                "pays only for what you use — no retainer, no per-seat fee. "
                "It's expert help at a fair hourly rate."
            ),
            "it_manager": (
                "{{ first_name }}, think of On-Demand as your escalation partner "
                "for the issues that are over your head or under your available "
                "time. We've all been there."
            ),
            "_default": (
                "{{ first_name }}, sometimes you just need someone good to fix "
                "the problem. MCRcore On-Demand is expert IT support with no "
                "contract and no commitment."
            ),
        },
    },

    "virtual_servers": {
        "subject_lines": [
            "{{ first_name }}, when is {{ company_name }}'s next server refresh?",
            "Cloud hosting for {{ industry }} — the alternative to buying hardware",
            "{{ company_name }} — what if your servers never needed replacing?",
        ],
        "openers": {
            "ceo_owner": (
                "{{ first_name }}, every server refresh at {{ company_name }} is "
                "a six-figure capital decision. Cloud hosting eliminates that "
                "cycle entirely — better performance, lower risk, predictable cost."
            ),
            "operations": (
                "{{ first_name }}, moving {{ company_name }}'s ERP and critical "
                "systems to cloud hosting means faster performance, accessible "
                "from every location, and no more worrying about hardware failure."
            ),
            "cfo_controller": (
                "{{ first_name }}, cloud hosting converts a CapEx hardware "
                "refresh into predictable monthly OpEx. Your peers in {{ industry }} "
                "love this because it smooths the P&L."
            ),
            "it_manager": (
                "{{ first_name }}, our virtual servers give you full admin "
                "access while we handle the underlying infrastructure — "
                "hardware, backups, DR, and monitoring. Best of both worlds."
            ),
            "_default": (
                "{{ first_name }}, virtual servers replace {{ company_name }}'s "
                "aging on-prem hardware with scalable, managed cloud "
                "infrastructure — including backups and 24/7 monitoring."
            ),
        },
    },

    "fractional_cio": {
        "subject_lines": [
            "{{ first_name }}, does {{ company_name }} have an IT strategy — or just IT support?",
            "C-level IT leadership at a fraction of the cost",
            "{{ company_name }} is making technology decisions. Who's guiding them?",
        ],
        "openers": {
            "ceo_owner": (
                "{{ first_name }}, you have a CFO for your finances. If "
                "{{ company_name }} is making six-figure technology decisions "
                "without equivalent IT leadership, that's a risk worth addressing."
            ),
            "operations": (
                "{{ first_name }}, when IT decisions are made reactively instead "
                "of strategically, operations feels it first — mismatched tools, "
                "disconnected systems, and projects that don't align with how "
                "you actually work."
            ),
            "cfo_controller": (
                "{{ first_name }}, a Fractional CIO ties every IT dollar to a "
                "business outcome. It's the difference between 'keeping the "
                "lights on' and 'investing in the right technology at the right "
                "time.'"
            ),
            "it_manager": (
                "{{ first_name }}, a Fractional CIO adds a strategic layer "
                "above day-to-day IT. You keep executing — and get help "
                "building the roadmap and making the case to leadership."
            ),
            "_default": (
                "{{ first_name }}, strategic IT leadership doesn't require a "
                "$200K salary. MCRcore's Fractional CIO brings planning, "
                "budgeting, and vendor management to {{ company_name }} at "
                "a fraction of that cost."
            ),
        },
    },

    "it_process_automation": {
        "subject_lines": [
            "{{ first_name }}, what's {{ company_name }}'s most time-consuming manual process?",
            "Reclaim 20+ hours a month at {{ company_name }}",
            "Automation isn't futuristic — it's how {{ industry }} leaders operate now",
        ],
        "openers": {
            "ceo_owner": (
                "{{ first_name }}, your team at {{ company_name }} is spending "
                "hours on tasks a well-built automation could handle in seconds. "
                "That's not just an efficiency issue — it's a growth constraint."
            ),
            "operations": (
                "{{ first_name }}, manual handoffs between systems are where "
                "errors happen, cycles slow down, and your team loses time they "
                "could spend on higher-value work."
            ),
            "cfo_controller": (
                "{{ first_name }}, automation doesn't replace headcount — it "
                "redeploys it. The hours your team spends on data entry and "
                "manual processes could be directed at revenue-generating work."
            ),
            "it_manager": (
                "{{ first_name }}, if you're spending your weekends writing "
                "provisioning scripts or manually syncing data between systems, "
                "there's a better way. Let us build the automations that just work."
            ),
            "_default": (
                "{{ first_name }}, the most impactful IT investment at "
                "{{ company_name }} might not be new hardware — it might be "
                "automating the manual processes that eat your team's time."
            ),
        },
    },

    "voip": {
        "subject_lines": [
            "{{ first_name }}, is {{ company_name }}'s phone system holding you back?",
            "Modern VOIP: less cost, more capability than your PBX",
            "{{ company_name }} — your phone system should work as hard as your team",
        ],
        "openers": {
            "ceo_owner": (
                "{{ first_name }}, unified communications across every "
                "{{ company_name }} location means one system, one bill, and "
                "zero legacy PBX headaches. It's a simple upgrade with immediate "
                "impact."
            ),
            "operations": (
                "{{ first_name }}, modern VOIP means multi-site call routing, "
                "mobile integration, and CRM-connected calls for your team. "
                "It's not just a phone — it's a communications platform."
            ),
            "cfo_controller": (
                "{{ first_name }}, replacing {{ company_name }}'s legacy PBX "
                "with cloud VOIP typically cuts telecom costs by 30-40% while "
                "adding features the old system couldn't provide."
            ),
            "it_manager": (
                "{{ first_name }}, a cloud-managed phone system means no "
                "on-prem PBX to babysit. Full admin portal, easy adds/moves, "
                "and we handle the infrastructure."
            ),
            "_default": (
                "{{ first_name }}, {{ company_name }}'s phone system should "
                "be a productivity tool — not a maintenance burden. Modern "
                "VOIP makes that possible."
            ),
        },
    },

    "wfh_implementation": {
        "subject_lines": [
            "{{ first_name }}, is {{ company_name }}'s remote setup secure — or just convenient?",
            "Hybrid work done right for {{ industry }} companies",
            "{{ company_name }} — secure remote access to your critical systems",
        ],
        "openers": {
            "ceo_owner": (
                "{{ first_name }}, enabling your team to work from anywhere "
                "is a competitive advantage — but only if it's secure. "
                "{{ company_name }}'s remote setup should protect the business "
                "as well as it enables productivity."
            ),
            "operations": (
                "{{ first_name }}, remote access to ERP and LOB applications "
                "doesn't have to mean VPN headaches and slow connections. "
                "Modern WFH implementation gives your team fast, secure access "
                "from any location."
            ),
            "cfo_controller": (
                "{{ first_name }}, enabling remote work at {{ company_name }} "
                "can reduce office footprint costs while keeping your team "
                "fully productive. The investment pays for itself in real estate "
                "savings alone."
            ),
            "it_manager": (
                "{{ first_name }}, deploying secure remote access at scale is "
                "a project, not a weekend task. We handle the VPN/ZTNA "
                "architecture, endpoint hardening, and policy deployment so "
                "you get a secure, managed remote workforce."
            ),
            "_default": (
                "{{ first_name }}, hybrid work is the standard now. The question "
                "is whether {{ company_name }}'s infrastructure is set up to "
                "support it securely and reliably."
            ),
        },
    },

    "technical_audit": {
        "subject_lines": [
            "{{ first_name }}, what would a 50-point IT inspection reveal at {{ company_name }}?",
            "Know exactly where {{ company_name }} stands before your next IT decision",
            "{{ company_name }} — the report your IT provider has never shown you",
        ],
        "openers": {
            "ceo_owner": (
                "{{ first_name }}, before {{ company_name }} makes its next "
                "IT investment, wouldn't it be useful to know exactly where "
                "you stand? Our Technical Audit gives you that clarity."
            ),
            "operations": (
                "{{ first_name }}, our Technical Audit delivers a scored "
                "report showing which systems at {{ company_name }} are solid "
                "and which are one failure away from stopping your operation."
            ),
            "cfo_controller": (
                "{{ first_name }}, our Technical Audit includes prioritized "
                "recommendations with cost estimates — so {{ company_name }} "
                "can budget IT fixes by business impact, not guesswork."
            ),
            "it_manager": (
                "{{ first_name }}, an independent Technical Audit is the "
                "third-party validation you need to get budget approval for "
                "the projects you already know need doing."
            ),
            "_default": (
                "{{ first_name }}, a comprehensive IT audit gives "
                "{{ company_name }} a scored, prioritized view of infrastructure, "
                "security, and operational readiness. It's the foundation for "
                "every smart IT decision."
            ),
        },
    },
}


# ===================================================================
# Helper Functions
# ===================================================================

def get_package_template(package_key: str) -> Optional[Dict]:
    """Return the full email template for a service package."""
    return PACKAGE_EMAIL_TEMPLATES.get(package_key)


def get_package_opener(package_key: str, title_key: str) -> str:
    """Get the title-specific opener for a package, with default fallback."""
    tpl = PACKAGE_EMAIL_TEMPLATES.get(package_key)
    if not tpl:
        return ""
    openers = tpl.get("openers", {})
    return openers.get(title_key, openers.get("_default", ""))


def get_package_block(package_key: str) -> Optional[Dict]:
    """Get the message block for a package (value prop, proof point, CTA)."""
    return PACKAGE_BLOCKS.get(package_key)


def get_package_subject_lines(package_key: str) -> List[str]:
    """Return subject line variants for a package."""
    tpl = PACKAGE_EMAIL_TEMPLATES.get(package_key)
    return tpl.get("subject_lines", []) if tpl else []


def build_package_email(
    package_key: str,
    title_key: str,
    context: Dict,
) -> Dict[str, str]:
    """
    Assemble a complete package-specific email from template blocks.

    Args:
        package_key: Service package ID (e.g. 'total_plan')
        title_key: Buyer title key (e.g. 'ceo_owner')
        context: Dict of Jinja2 placeholder values

    Returns:
        Dict with 'subject', 'body' keys (still containing unfilled placeholders
        that the agent will resolve via LLM personalization).
    """
    tpl = PACKAGE_EMAIL_TEMPLATES.get(package_key)
    pkg_block = PACKAGE_BLOCKS.get(package_key)
    if not tpl or not pkg_block:
        return {"subject": "", "body": ""}

    # Select subject line (first variant as default)
    subject = tpl["subject_lines"][0]

    # Get title-specific opener
    openers = tpl.get("openers", {})
    opener = openers.get(title_key, openers.get("_default", ""))

    # Get title-specific angle from package block
    title_angle = pkg_block.get("title_angles", {}).get(title_key, "")

    # Get CTA (first variant as default)
    cta = pkg_block.get("cta_variants", [""])[0]

    body = (
        f"{opener}\n\n"
        f"{pkg_block['value_prop']}\n\n"
        f"{title_angle}\n\n"
        f"{{{{ differentiator_block }}}}\n\n"
        f"{pkg_block['proof_point']}\n\n"
        f"{cta}\n\n"
        f"Best,\n"
        f"{{{{ sender_name }}}}\n"
        f"{{{{ sender_title }}}}, MCRcore\n"
        f"{COMPLIANCE_FOOTER}"
    )

    return {"subject": subject, "body": body}


def list_available_packages() -> List[str]:
    """Return all available package template keys."""
    return list(PACKAGE_EMAIL_TEMPLATES.keys())
