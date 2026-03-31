"""
MCRcore Growth Engine - Microsoft Teams Notifier

Sends messages and Adaptive Cards to Microsoft Teams channels via
incoming webhook connectors.

All functions accept an optional webhook_url parameter; if omitted
the MS_TEAMS_WEBHOOK_URL environment variable is used.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from src.utils.logger import setup_logger

load_dotenv()

logger = setup_logger("mcr_growth_engine.teams_notifier")

DEFAULT_WEBHOOK_URL = os.getenv(
    "MS_TEAMS_WEBHOOK_URL",
    "PLACEHOLDER_https://outlook.office.com/webhook/your-webhook-url",
)


def _post_to_webhook(payload: dict, webhook_url: str = None) -> bool:
    """
    Post a JSON payload to the Teams webhook.

    Args:
        payload: The card / message payload dict.
        webhook_url: Override webhook URL.

    Returns:
        True if the webhook accepted the message (HTTP 200).
    """
    url = webhook_url or DEFAULT_WEBHOOK_URL

    if "PLACEHOLDER" in url:
        logger.warning("Teams webhook URL is still a PLACEHOLDER - skipping send")
        return False

    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            logger.info("Teams message sent successfully")
            return True
        else:
            logger.error(
                f"Teams webhook returned {resp.status_code}: {resp.text}"
            )
            return False
    except requests.RequestException as e:
        logger.error(f"Teams webhook request failed: {e}")
        return False


def _wrap_adaptive_card(body: list, actions: list = None) -> dict:
    """
    Wrap body elements and optional actions into a Teams Adaptive Card
    attachment envelope.

    Returns the full payload ready for webhook POST.
    """
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
    }
    if actions:
        card["actions"] = actions

    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": card,
            }
        ],
    }
    return payload


# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------

def send_teams_message(message: str, webhook_url: str = None) -> bool:
    """
    Send a simple text message to Teams.

    Args:
        message: Plain-text message body.
        webhook_url: Optional webhook URL override.

    Returns:
        True on success.
    """
    body = [
        {
            "type": "TextBlock",
            "text": message,
            "wrap": True,
        }
    ]
    payload = _wrap_adaptive_card(body)
    logger.info(f"Sending simple Teams message ({len(message)} chars)")
    return _post_to_webhook(payload, webhook_url)


def send_teams_card(
    title: str,
    facts: List[Dict[str, str]],
    actions: List[Dict[str, Any]] = None,
    webhook_url: str = None,
) -> bool:
    """
    Send an Adaptive Card with a title, fact set, and optional action buttons.

    Args:
        title: Card title text.
        facts: List of dicts with 'title' and 'value' keys.
                e.g. [{"title": "Pipeline", "value": "$1.2M"}]
        actions: Optional list of Adaptive Card action objects.
                 e.g. [{"type": "Action.OpenUrl", "title": "View", "url": "..."}]
        webhook_url: Optional webhook URL override.

    Returns:
        True on success.
    """
    body = [
        {
            "type": "TextBlock",
            "size": "Large",
            "weight": "Bolder",
            "text": title,
            "wrap": True,
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": f["title"], "value": str(f["value"])}
                for f in facts
            ],
        },
    ]

    card_actions = None
    if actions:
        card_actions = actions

    payload = _wrap_adaptive_card(body, card_actions)
    logger.info(f"Sending Teams card: {title}")
    return _post_to_webhook(payload, webhook_url)


def send_escalation_alert(
    opportunity_summary: Dict[str, Any],
    webhook_url: str = None,
) -> bool:
    """
    Send a high-priority escalation alert for an opportunity that
    needs human attention.

    Args:
        opportunity_summary: Dict with keys like 'company', 'value',
            'reason', 'contact', 'recommended_action'.
        webhook_url: Optional webhook URL override.

    Returns:
        True on success.
    """
    company = opportunity_summary.get("company", "Unknown")
    value = opportunity_summary.get("value", "N/A")
    reason = opportunity_summary.get("reason", "Requires review")
    contact = opportunity_summary.get("contact", "N/A")
    action = opportunity_summary.get("recommended_action", "Review opportunity")

    body = [
        {
            "type": "TextBlock",
            "size": "Large",
            "weight": "Bolder",
            "text": "🚨 Escalation Alert",
            "color": "Attention",
            "wrap": True,
        },
        {
            "type": "TextBlock",
            "text": f"An opportunity requires your immediate attention.",
            "wrap": True,
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Company", "value": str(company)},
                {"title": "Value", "value": str(value)},
                {"title": "Contact", "value": str(contact)},
                {"title": "Reason", "value": str(reason)},
                {"title": "Recommended Action", "value": str(action)},
            ],
        },
        {
            "type": "TextBlock",
            "text": f"Escalated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "size": "Small",
            "isSubtle": True,
            "wrap": True,
        },
    ]

    card_actions = [
        {
            "type": "Action.OpenUrl",
            "title": "Review in Dashboard",
            "url": opportunity_summary.get("dashboard_url", "https://mcr-dashboard.example.com"),
        },
    ]

    payload = _wrap_adaptive_card(body, card_actions)
    logger.info(f"Sending escalation alert for {company}")
    return _post_to_webhook(payload, webhook_url)


def send_daily_kpi(
    kpi_data: Dict[str, Any],
    webhook_url: str = None,
) -> bool:
    """
    Send a daily KPI summary card to the Teams channel.

    Args:
        kpi_data: Dict with KPI metrics. Expected keys (all optional):
            - leads_generated, emails_sent, replies_received,
            - meetings_booked, pipeline_value, conversion_rate,
            - bounce_rate, period
        webhook_url: Optional webhook URL override.

    Returns:
        True on success.
    """
    period = kpi_data.get("period", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    facts = []
    kpi_labels = {
        "leads_generated": "Leads Generated",
        "emails_sent": "Emails Sent",
        "replies_received": "Replies Received",
        "meetings_booked": "Meetings Booked",
        "pipeline_value": "Pipeline Value",
        "conversion_rate": "Conversion Rate",
        "bounce_rate": "Bounce Rate",
    }
    for key, label in kpi_labels.items():
        if key in kpi_data:
            facts.append({"title": label, "value": str(kpi_data[key])})

    body = [
        {
            "type": "TextBlock",
            "size": "Large",
            "weight": "Bolder",
            "text": f"📊 Daily KPI Report — {period}",
            "wrap": True,
        },
        {
            "type": "FactSet",
            "facts": facts,
        },
        {
            "type": "TextBlock",
            "text": f"Generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "size": "Small",
            "isSubtle": True,
            "wrap": True,
        },
    ]

    payload = _wrap_adaptive_card(body)
    logger.info(f"Sending daily KPI report for {period}")
    return _post_to_webhook(payload, webhook_url)


def send_approval_request(
    request_type: str,
    details: Dict[str, Any],
    webhook_url: str = None,
) -> bool:
    """
    Send an approval request card with Accept/Reject action buttons.

    Args:
        request_type: Type of request, e.g. 'email_campaign', 'budget_increase',
            'new_sequence', 'lead_qualification_override'.
        details: Dict with request-specific details. Common keys:
            - description, requester, items, estimated_impact, approval_url, reject_url
        webhook_url: Optional webhook URL override.

    Returns:
        True on success.
    """
    description = details.get("description", "Approval needed")
    requester = details.get("requester", "Growth Engine Agent")
    approval_url = details.get("approval_url", "https://mcr-dashboard.example.com/approve")
    reject_url = details.get("reject_url", "https://mcr-dashboard.example.com/reject")

    facts = [
        {"title": "Request Type", "value": request_type},
        {"title": "Requested By", "value": requester},
    ]
    # Add any extra detail fields
    for key, value in details.items():
        if key not in ("description", "requester", "approval_url", "reject_url"):
            # Convert key from snake_case to Title Case
            label = key.replace("_", " ").title()
            facts.append({"title": label, "value": str(value)})

    body = [
        {
            "type": "TextBlock",
            "size": "Large",
            "weight": "Bolder",
            "text": "✅ Approval Request",
            "wrap": True,
        },
        {
            "type": "TextBlock",
            "text": description,
            "wrap": True,
        },
        {
            "type": "FactSet",
            "facts": facts,
        },
        {
            "type": "TextBlock",
            "text": f"Requested at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "size": "Small",
            "isSubtle": True,
            "wrap": True,
        },
    ]

    card_actions = [
        {
            "type": "Action.OpenUrl",
            "title": "✅ Approve",
            "url": approval_url,
            "style": "positive",
        },
        {
            "type": "Action.OpenUrl",
            "title": "❌ Reject",
            "url": reject_url,
            "style": "destructive",
        },
    ]

    payload = _wrap_adaptive_card(body, card_actions)
    logger.info(f"Sending approval request: {request_type}")
    return _post_to_webhook(payload, webhook_url)
