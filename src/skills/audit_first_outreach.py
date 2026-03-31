"""
MCRcore Growth Engine - Audit-First Outreach Skill

Provides Jinja2-ready email templates for the audit-first engagement model:
  - Cold outreach templates by buyer title (CEO, Ops, CFO, IT Mgr)
  - CTA variants (free diagnostic, no-cost systems review, 30-min walkthrough)
  - Follow-up angle variations for 7-day, 30-day, and 90-day nurture
  - All templates use {{ placeholders }} for personalization by the agent

Philosophy: Lead with value (the audit), not a sales pitch. Every email
should sound like it was written by someone who understands the prospect's
business — because the agent that generates it does.
"""

from typing import Dict, List


# ===================================================================
# CTA Variants for Audit-First Emails
# ===================================================================

CTA_VARIANTS: Dict[str, str] = {
    "free_diagnostic": (
        "I'd like to offer {{ company_name }} a complimentary IT diagnostic — "
        "a structured review of your infrastructure, security posture, and "
        "operational readiness. No cost, no obligation, and the report is yours "
        "regardless of next steps. Worth 30 minutes?"
    ),
    "no_cost_systems_review": (
        "We're offering a no-cost systems review for {{ industry }} companies "
        "in your region. It's a scored assessment covering network, security, "
        "backups, and compliance — the kind of report your current provider "
        "has probably never produced. Interested?"
    ),
    "30_min_walkthrough": (
        "I'd love to walk you through what a 50-point IT audit looks like — "
        "it takes about 30 minutes and I can show you exactly what we'd "
        "examine at {{ company_name }}. No prep needed on your end. "
        "Would {{ preferred_day }} work?"
    ),
}


# ===================================================================
# Cold Audit-First Email Templates by Title
# ===================================================================

AUDIT_FIRST_TEMPLATES: Dict[str, Dict] = {

    "ceo_owner": {
        "subject_lines": [
            "{{ first_name }}, quick question about {{ company_name }}'s IT risk exposure",
            "What a 50-point IT audit reveals at companies like {{ company_name }}",
            "{{ company_name }} — one thing your IT provider has never shown you",
        ],
        "body": (
            "{{ first_name }},\n\n"
            "{{ opener }}\n\n"
            "I'm reaching out because we work with {{ industry }} companies "
            "at {{ company_name }}'s stage, and a pattern keeps showing up: "
            "business leaders are making growth decisions without a clear picture "
            "of their IT readiness — or the risks hiding in their current setup.\n\n"
            "{{ differentiator_block }}\n\n"
            "That's why we lead with an audit, not a sales pitch. Our Technical "
            "Audit is a structured, 50-point assessment covering infrastructure, "
            "security, backups, and compliance. You get a scored report with "
            "prioritized recommendations — and it's yours regardless of whether "
            "you work with us.\n\n"
            "{{ cta }}\n\n"
            "Best,\n"
            "{{ sender_name }}\n"
            "{{ sender_title }}, MCRcore\n"
            "{{ compliance_footer }}"
        ),
    },

    "operations": {
        "subject_lines": [
            "{{ first_name }}, how much does unplanned downtime cost {{ company_name }}?",
            "{{ company_name }}'s systems — solid or one failure away from a bad day?",
            "A free infrastructure check for {{ company_name }} — no strings",
        ],
        "body": (
            "{{ first_name }},\n\n"
            "{{ opener }}\n\n"
            "In my experience with {{ industry }} operations teams, the biggest "
            "IT risks aren't the ones you know about — they're the ones your "
            "current provider hasn't looked for. Aging firmware, unpatched "
            "endpoints, backup jobs that silently fail. Any one of them can "
            "take your operation offline without warning.\n\n"
            "{{ differentiator_block }}\n\n"
            "Our Technical Audit is designed to surface exactly those risks. "
            "It covers infrastructure, security, network health, and backup "
            "integrity — and the report includes a Red/Yellow/Green scorecard "
            "so you know exactly where you stand.\n\n"
            "{{ cta }}\n\n"
            "Best,\n"
            "{{ sender_name }}\n"
            "{{ sender_title }}, MCRcore\n"
            "{{ compliance_footer }}"
        ),
    },

    "cfo_controller": {
        "subject_lines": [
            "{{ first_name }}, the hidden cost of 'IT is fine' at {{ company_name }}",
            "What undocumented IT risk is costing {{ company_name }} — and how to quantify it",
            "{{ company_name }} — an IT risk assessment with actual numbers",
        ],
        "body": (
            "{{ first_name }},\n\n"
            "{{ opener }}\n\n"
            "The {{ industry }} CFOs I work with tell me the same thing: IT "
            "feels like a black box. Costs are unpredictable, risk is hard to "
            "quantify, and there's no documentation that would satisfy an auditor "
            "or a cyber insurance carrier.\n\n"
            "{{ differentiator_block }}\n\n"
            "Our Technical Audit changes that. It delivers a scored report "
            "covering security, infrastructure, and compliance — with cost "
            "estimates for remediation prioritized by business impact. It's the "
            "kind of document you can hand to your auditor, your insurer, or "
            "your board.\n\n"
            "{{ cta }}\n\n"
            "Best,\n"
            "{{ sender_name }}\n"
            "{{ sender_title }}, MCRcore\n"
            "{{ compliance_footer }}"
        ),
    },

    "it_manager": {
        "subject_lines": [
            "{{ first_name }}, an independent second opinion on {{ company_name }}'s infrastructure",
            "Getting budget for the projects you already know need doing",
            "{{ first_name }} — a free audit that makes your case to leadership",
        ],
        "body": (
            "{{ first_name }},\n\n"
            "{{ opener }}\n\n"
            "I know how it goes: you see the risks, you know what needs to "
            "be fixed, but getting budget approval requires more than your "
            "gut feeling. Leadership wants documentation, prioritization, "
            "and third-party validation.\n\n"
            "{{ differentiator_block }}\n\n"
            "That's exactly what our Technical Audit provides. An independent, "
            "scored assessment of {{ company_name }}'s infrastructure, security, "
            "and operational readiness — with a prioritized recommendation "
            "roadmap you can take straight to leadership.\n\n"
            "Think of it as ammunition for the budget conversation you've been "
            "wanting to have.\n\n"
            "{{ cta }}\n\n"
            "Best,\n"
            "{{ sender_name }}\n"
            "{{ sender_title }}, MCRcore\n"
            "{{ compliance_footer }}"
        ),
    },
}


# ===================================================================
# Follow-Up Angle Variations (7 / 30 / 90 day nurture)
# ===================================================================

FOLLOWUP_TEMPLATES: Dict[str, Dict] = {

    "day_7": {
        "label": "7-Day Follow-Up — Light Nudge + New Angle",
        "subject_lines": [
            "Re: {{ original_subject }}",
            "{{ first_name }}, one quick thought on {{ company_name }}'s IT",
            "Following up — still worth a look?",
        ],
        "angles": {
            "social_proof": (
                "{{ first_name }},\n\n"
                "I wanted to follow up briefly on my note last week.\n\n"
                "Since then, we completed an audit for another {{ industry }} "
                "company similar to {{ company_name }} — and uncovered 4 critical "
                "risks their previous IT provider had missed entirely. Fixable "
                "issues, but ones that would have been expensive if they'd turned "
                "into incidents.\n\n"
                "I don't know if {{ company_name }} has the same exposure, but "
                "the audit would tell us. Still interested in a quick look?\n\n"
                "{{ cta }}\n\n"
                "Best,\n"
                "{{ sender_name }}\n"
                "{{ sender_title }}, MCRcore\n"
                "{{ compliance_footer }}"
            ),
            "cost_of_inaction": (
                "{{ first_name }},\n\n"
                "Quick follow-up. One stat that stuck with me this week:\n\n"
                "The average cost of a single hour of unplanned downtime for a "
                "{{ industry }} company {{ company_name }}'s size is between "
                "$10,000 and $50,000. And most companies don't know they're at "
                "risk until after the outage.\n\n"
                "Our Technical Audit identifies those risks before they become "
                "incidents — and the report is free.\n\n"
                "{{ cta }}\n\n"
                "Best,\n"
                "{{ sender_name }}\n"
                "{{ sender_title }}, MCRcore\n"
                "{{ compliance_footer }}"
            ),
            "new_resource": (
                "{{ first_name }},\n\n"
                "Following up with something useful. We just published a quick "
                "guide on the top 5 IT risks {{ industry }} companies miss — "
                "it's a 2-minute read.\n\n"
                "{{ resource_link }}\n\n"
                "If anything in there resonates for {{ company_name }}, our "
                "Technical Audit digs into all of it. Happy to set one up.\n\n"
                "Best,\n"
                "{{ sender_name }}\n"
                "{{ sender_title }}, MCRcore\n"
                "{{ compliance_footer }}"
            ),
        },
    },

    "day_30": {
        "label": "30-Day Follow-Up — Fresh Value + Different Frame",
        "subject_lines": [
            "{{ first_name }}, quick update relevant to {{ company_name }}",
            "New data on {{ industry }} IT risk — thought of {{ company_name }}",
            "{{ first_name }}, a different way to think about IT at {{ company_name }}",
        ],
        "angles": {
            "industry_trend": (
                "{{ first_name }},\n\n"
                "I reached out about a month ago regarding {{ company_name }}'s "
                "IT posture. I wanted to circle back with a different angle.\n\n"
                "We're seeing a clear trend in {{ industry }}: companies that "
                "run proactive IT audits are catching compliance gaps, security "
                "exposures, and infrastructure risks that save them 5-10x the "
                "cost of remediation if caught later.\n\n"
                "{{ differentiator_block }}\n\n"
                "No pitch — just a structured assessment that gives you clarity. "
                "Is it worth revisiting?\n\n"
                "{{ cta }}\n\n"
                "Best,\n"
                "{{ sender_name }}\n"
                "{{ sender_title }}, MCRcore\n"
                "{{ compliance_footer }}"
            ),
            "leadership_perspective": (
                "{{ first_name }},\n\n"
                "A month ago I suggested an IT audit for {{ company_name }}. "
                "I wanted to share a thought from a conversation I had with "
                "another {{ title_category }} this week.\n\n"
                "They told me: 'I didn't know what I didn't know about our IT "
                "— and once I saw the audit report, I couldn't un-see it.'\n\n"
                "That's the value of an independent assessment. Not a sales "
                "pitch — a mirror. Would it be useful for {{ company_name }}?\n\n"
                "{{ cta }}\n\n"
                "Best,\n"
                "{{ sender_name }}\n"
                "{{ sender_title }}, MCRcore\n"
                "{{ compliance_footer }}"
            ),
            "package_intro": (
                "{{ first_name }},\n\n"
                "I reached out last month about a Technical Audit for "
                "{{ company_name }}. Since then, I've been thinking about what "
                "specifically might be most relevant to you.\n\n"
                "{{ package_value_prop }}\n\n"
                "The audit is still the best starting point — it tells us "
                "(and you) exactly where the gaps are and what to prioritize. "
                "Would it be worth scheduling?\n\n"
                "{{ cta }}\n\n"
                "Best,\n"
                "{{ sender_name }}\n"
                "{{ sender_title }}, MCRcore\n"
                "{{ compliance_footer }}"
            ),
        },
    },

    "day_90": {
        "label": "90-Day Follow-Up — Materially Different, Reset Conversation",
        "subject_lines": [
            "{{ first_name }}, checking in with fresh eyes",
            "Things change in 90 days — has anything shifted at {{ company_name }}?",
            "{{ first_name }}, new offer for {{ company_name }}",
        ],
        "angles": {
            "trigger_event": (
                "{{ first_name }},\n\n"
                "It's been a few months since we last connected. A lot can "
                "change in a quarter — new projects, new leadership, new "
                "challenges.\n\n"
                "{{ trigger_context }}\n\n"
                "If {{ company_name }}'s IT situation has shifted at all — "
                "or if you're heading into a planning cycle — our no-cost "
                "Technical Audit is still on the table. It's the fastest way "
                "to get a clear-eyed view of where things stand.\n\n"
                "{{ cta }}\n\n"
                "Best,\n"
                "{{ sender_name }}\n"
                "{{ sender_title }}, MCRcore\n"
                "{{ compliance_footer }}"
            ),
            "competitor_gap": (
                "{{ first_name }},\n\n"
                "I wanted to reach out with a different lens.\n\n"
                "We've been working with several {{ industry }} companies this "
                "quarter, and a common theme keeps surfacing: IT providers that "
                "look fine on the surface but haven't run a real infrastructure "
                "audit in years. The gap between 'things seem fine' and 'things "
                "are actually solid' is where the risk hides.\n\n"
                "{{ differentiator_block }}\n\n"
                "Even if {{ company_name }} is happy with the current setup, "
                "an independent audit has standalone value. Would it be worth "
                "30 minutes?\n\n"
                "{{ cta }}\n\n"
                "Best,\n"
                "{{ sender_name }}\n"
                "{{ sender_title }}, MCRcore\n"
                "{{ compliance_footer }}"
            ),
            "fresh_offer": (
                "{{ first_name }},\n\n"
                "I'm reaching back out to {{ company_name }} with something "
                "new.\n\n"
                "{{ new_offer_context }}\n\n"
                "Whether or not this is relevant, our standing offer for a "
                "complimentary Technical Audit remains open. It's the best way "
                "to know exactly where {{ company_name }} stands — and the "
                "report is yours regardless.\n\n"
                "{{ cta }}\n\n"
                "Best,\n"
                "{{ sender_name }}\n"
                "{{ sender_title }}, MCRcore\n"
                "{{ compliance_footer }}"
            ),
        },
    },
}


# ===================================================================
# Helper: Get all templates for a given title and stage
# ===================================================================

def get_audit_template(title_key: str) -> Dict:
    """Return the cold audit-first template for a buyer title."""
    return AUDIT_FIRST_TEMPLATES.get(title_key, AUDIT_FIRST_TEMPLATES["ceo_owner"])


def get_followup_template(stage: str) -> Dict:
    """Return the follow-up template dict for a nurture stage."""
    return FOLLOWUP_TEMPLATES.get(stage, FOLLOWUP_TEMPLATES["day_7"])


def get_cta(variant: str = "free_diagnostic") -> str:
    """Return a CTA variant string."""
    return CTA_VARIANTS.get(variant, CTA_VARIANTS["free_diagnostic"])


def list_available_stages() -> List[str]:
    """Return available nurture stages."""
    return ["first_touch"] + list(FOLLOWUP_TEMPLATES.keys())


def list_followup_angles(stage: str) -> List[str]:
    """Return available angle keys for a given follow-up stage."""
    tpl = FOLLOWUP_TEMPLATES.get(stage)
    if tpl:
        return list(tpl["angles"].keys())
    return []
