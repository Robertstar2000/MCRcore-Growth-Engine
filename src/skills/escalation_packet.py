"""
MCRcore Growth Engine - Escalation Packet Skill

Templates for internal escalation summaries, communication timelines,
action recommendation checklists, and value estimation rules.
Pure functions and data — no DB dependency.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Internal Summary Template (plain text for email)
# ---------------------------------------------------------------------------

INTERNAL_SUMMARY_TEMPLATE = """\
====================================================================
  MCRcore Growth Engine — Opportunity Escalation
====================================================================

ESCALATION ID:   {opportunity_id}
ESCALATED AT:    {escalated_at}
ESCALATED TO:    {escalated_to}

--------------------------------------------------------------------
  COMPANY INFORMATION
--------------------------------------------------------------------
Company:         {company_name}
Domain:          {domain}
Industry:        {industry}
Employee Band:   {employee_band}
Geography:       {geography}
Website:         {website_url}

--------------------------------------------------------------------
  CONTACT INFORMATION
--------------------------------------------------------------------
Name:            {contact_name}
Title:           {contact_title}
Email:           {contact_email}
Profile URL:     {profile_url}

--------------------------------------------------------------------
  SCORING SUMMARY
--------------------------------------------------------------------
Fit Score:           {fit_score}/100
Need Score:          {need_score}/100
Engagement Score:    {engagement_score}/100
Package Fit Score:   {package_fit_score}/100
Sales Probability:   {sales_probability}%
Priority Tier:       {priority_tier}
Margin Band:         {margin_band}

--------------------------------------------------------------------
  RECOMMENDATION
--------------------------------------------------------------------
Recommended Package:     {recommended_package}
Estimated Value Band:    {estimated_value_band}
Estimated Margin Band:   {estimated_margin_band}
Recommended Entry CTA:   {recommended_entry_cta}

--------------------------------------------------------------------
  COMMUNICATION HISTORY
--------------------------------------------------------------------
{communication_timeline}

--------------------------------------------------------------------
  RECOMMENDED NEXT ACTION
--------------------------------------------------------------------
{recommended_action}

--------------------------------------------------------------------
  REPLY THAT TRIGGERED ESCALATION
--------------------------------------------------------------------
{trigger_reply_text}

====================================================================
  This escalation was generated automatically by MCRcore Growth Engine.
  Please respond within 24 hours.
====================================================================
"""


# ---------------------------------------------------------------------------
# Communication Timeline Template
# ---------------------------------------------------------------------------

TIMELINE_ENTRY_TEMPLATE = """\
  [{timestamp}] {event_type}: {summary}
"""

TIMELINE_HEADER = "  Date/Time               Type            Summary\n  " + "-" * 60


def format_communication_timeline(events: List[Dict[str, Any]]) -> str:
    """
    Format a list of communication events into a plain-text timeline.

    Each event dict should have:
        - timestamp (str or datetime)
        - event_type (str): e.g. 'outreach_sent', 'reply_received', 'open', 'click'
        - summary (str): brief description

    Returns a formatted string.
    """
    if not events:
        return "  No communication history recorded."

    lines = [TIMELINE_HEADER]
    for event in events:
        ts = event.get("timestamp", "")
        if isinstance(ts, datetime):
            ts = ts.strftime("%Y-%m-%d %H:%M UTC")
        event_type = event.get("event_type", "unknown").ljust(16)
        summary = event.get("summary", "")
        lines.append(f"  [{ts}] {event_type} {summary}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Action Recommendation Checklist
# ---------------------------------------------------------------------------

ACTION_CHECKLIST_TEMPLATE = """\
RECOMMENDED ACTIONS:
  [ ] {primary_action}
  [ ] Review communication history below
  [ ] Verify contact information is current
  [ ] Check CRM for any existing relationship
{additional_actions}

TIMING:
  Response within: {response_sla}
  Follow-up if no response: {follow_up_deadline}

TALKING POINTS:
{talking_points}
"""


def build_action_checklist(
    primary_action: str,
    additional_actions: List[str] = None,
    response_sla: str = "24 hours",
    follow_up_deadline: str = "48 hours",
    talking_points: List[str] = None,
) -> str:
    """
    Build a formatted action recommendation checklist.

    Args:
        primary_action: The main recommended action.
        additional_actions: Extra action items.
        response_sla: How soon to respond.
        follow_up_deadline: When to follow up if no response.
        talking_points: Key conversation points.

    Returns:
        Formatted checklist string.
    """
    extra = ""
    if additional_actions:
        for action in additional_actions:
            extra += f"  [ ] {action}\n"

    points = ""
    if talking_points:
        for point in talking_points:
            points += f"  - {point}\n"
    else:
        points = "  - Reference their specific reply / interest\n"
        points += "  - Confirm their needs align with recommended package\n"
        points += "  - Offer to schedule a brief discovery call\n"

    return ACTION_CHECKLIST_TEMPLATE.format(
        primary_action=primary_action,
        additional_actions=extra,
        response_sla=response_sla,
        follow_up_deadline=follow_up_deadline,
        talking_points=points,
    )


# ---------------------------------------------------------------------------
# Value Estimation Rules
# ---------------------------------------------------------------------------

# MCRcore package value bands (monthly recurring revenue)
PACKAGE_VALUE_BANDS = {
    "total_plan": {
        "low": 3000,
        "mid": 5000,
        "high": 10000,
        "label": "$3K-$10K/mo",
        "margin_band": "high",
    },
    "proactive_monitoring": {
        "low": 1500,
        "mid": 3000,
        "high": 6000,
        "label": "$1.5K-$6K/mo",
        "margin_band": "high",
    },
    "essential_cybersecurity": {
        "low": 500,
        "mid": 1500,
        "high": 3000,
        "label": "$500-$3K/mo",
        "margin_band": "low-wedge",
    },
    "virtual_servers": {
        "low": 1000,
        "mid": 2500,
        "high": 5000,
        "label": "$1K-$5K/mo",
        "margin_band": "medium",
    },
    "fractional_cio": {
        "low": 2000,
        "mid": 4000,
        "high": 8000,
        "label": "$2K-$8K/mo",
        "margin_band": "high",
    },
    "it_process_automation": {
        "low": 2000,
        "mid": 5000,
        "high": 12000,
        "label": "$2K-$12K/mo",
        "margin_band": "high",
    },
    "wfh_implementation": {
        "low": 1000,
        "mid": 2000,
        "high": 4000,
        "label": "$1K-$4K/mo",
        "margin_band": "medium",
    },
    "voip": {
        "low": 500,
        "mid": 1500,
        "high": 3000,
        "label": "$500-$3K/mo",
        "margin_band": "medium",
    },
    "on_demand_break_fix": {
        "low": 200,
        "mid": 800,
        "high": 2000,
        "label": "$200-$2K/mo",
        "margin_band": "tentative",
    },
    "technical_audit": {
        "low": 2000,
        "mid": 5000,
        "high": 10000,
        "label": "$2K-$10K (one-time)",
        "margin_band": "variable",
    },
}

# Employee band multipliers for value estimation
EMPLOYEE_BAND_MULTIPLIERS = {
    "1-10": 0.6,
    "10-25": 0.8,
    "25-50": 1.0,
    "50-100": 1.3,
    "100-200": 1.6,
    "200-500": 2.0,
    "500+": 2.5,
}


def estimate_opportunity_value(
    package_id: str,
    employee_band: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Estimate the value band for an opportunity based on package and company size.

    Args:
        package_id: Service package identifier.
        employee_band: Company employee band string (e.g. '50-100').

    Returns:
        Dict with estimated_low, estimated_mid, estimated_high,
        value_band_label, margin_band, annual_estimate.
    """
    package = PACKAGE_VALUE_BANDS.get(package_id)
    if not package:
        return {
            "estimated_low": 0,
            "estimated_mid": 0,
            "estimated_high": 0,
            "value_band_label": "Unknown package",
            "margin_band": "variable",
            "annual_estimate": 0,
        }

    multiplier = 1.0
    if employee_band:
        multiplier = EMPLOYEE_BAND_MULTIPLIERS.get(employee_band, 1.0)

    low = int(package["low"] * multiplier)
    mid = int(package["mid"] * multiplier)
    high = int(package["high"] * multiplier)

    return {
        "estimated_low": low,
        "estimated_mid": mid,
        "estimated_high": high,
        "value_band_label": f"${low:,}-${high:,}/mo",
        "margin_band": package["margin_band"],
        "annual_estimate": mid * 12,
    }


def build_escalation_summary(
    opportunity_data: Dict[str, Any],
    communication_events: List[Dict[str, Any]],
    action_recommendation: str,
) -> str:
    """
    Build a complete escalation summary using the internal template.

    Args:
        opportunity_data: Dict with all opportunity, lead, company, contact,
                          and score fields.
        communication_events: List of timeline event dicts.
        action_recommendation: Formatted action checklist string.

    Returns:
        Formatted escalation summary string.
    """
    timeline_str = format_communication_timeline(communication_events)

    # Provide defaults for all template fields
    defaults = {
        "opportunity_id": "N/A",
        "escalated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "escalated_to": "Sales Team",
        "company_name": "Unknown",
        "domain": "N/A",
        "industry": "N/A",
        "employee_band": "N/A",
        "geography": "N/A",
        "website_url": "N/A",
        "contact_name": "Unknown",
        "contact_title": "N/A",
        "contact_email": "N/A",
        "profile_url": "N/A",
        "fit_score": "N/A",
        "need_score": "N/A",
        "engagement_score": "N/A",
        "package_fit_score": "N/A",
        "sales_probability": "N/A",
        "priority_tier": "N/A",
        "margin_band": "N/A",
        "recommended_package": "N/A",
        "estimated_value_band": "N/A",
        "estimated_margin_band": "N/A",
        "recommended_entry_cta": "N/A",
        "trigger_reply_text": "N/A",
    }

    # Merge opportunity data over defaults
    template_data = {**defaults, **opportunity_data}
    template_data["communication_timeline"] = timeline_str
    template_data["recommended_action"] = action_recommendation

    return INTERNAL_SUMMARY_TEMPLATE.format(**template_data)
