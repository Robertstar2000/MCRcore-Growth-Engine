"""
MCRcore Growth Engine - Analytics & Reporting Skill

Calculates daily KPIs, builds funnel reports, detects anomalies, and
formats summary output for Teams and logging.

KPI Definitions:
    leads_acquired, leads_enriched, leads_scored, outreach_sent,
    replies_received, positive_replies, opportunities_created,
    opportunities_escalated, opt_outs, bounces, nurture_scheduled,
    nurture_sent

Funnel Stages:
    new -> enriched -> scored -> outreach -> replied -> opportunity
    -> escalated -> won/lost
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from db.models import (
    Lead,
    NurtureSchedule,
    Opportunity,
    OutreachEvent,
    ReplyEvent,
    SuppressionRecord,
)
from db.repositories import (
    LeadRepository,
    NurtureRepository,
    OpportunityRepository,
    OutreachRepository,
    ReplyRepository,
    SuppressionRepository,
)

# ===================================================================
# KPI Key Definitions
# ===================================================================
KPI_KEYS: List[str] = [
    "leads_acquired",
    "leads_enriched",
    "leads_scored",
    "outreach_sent",
    "replies_received",
    "positive_replies",
    "opportunities_created",
    "opportunities_escalated",
    "opt_outs",
    "bounces",
    "nurture_scheduled",
    "nurture_sent",
]

# ===================================================================
# Funnel Stage Definitions
# ===================================================================
FUNNEL_STAGES: List[str] = [
    "new",
    "enriched",
    "scored",
    "outreach",
    "replied",
    "opportunity",
    "escalated",
    "won",
    "lost",
]

# Maps lead status values to their funnel stage bucket
STATUS_TO_FUNNEL: Dict[str, str] = {
    "new": "new",
    "enriched": "enriched",
    "scored": "scored",
    "outreach": "outreach",
    "outreach_sent": "outreach",
    "replied": "replied",
    "qualified": "opportunity",
    "opportunity": "opportunity",
    "escalated": "escalated",
    "won": "won",
    "closed_won": "won",
    "lost": "lost",
    "closed_lost": "lost",
}

# ===================================================================
# Anomaly Thresholds
# ===================================================================
ANOMALY_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "reply_rate": {
        "operator": "lt",
        "threshold": 1.0,  # percent
        "severity": "warning",
        "message": "Reply rate is below 1% — outreach quality may need review",
    },
    "bounce_rate": {
        "operator": "gt",
        "threshold": 5.0,  # percent
        "severity": "alert",
        "message": "Bounce rate exceeds 5% — email list hygiene issue",
    },
    "opt_out_rate": {
        "operator": "gt",
        "threshold": 3.0,  # percent
        "severity": "alert",
        "message": "Opt-out rate exceeds 3% — messaging may need adjustment",
    },
}


# ===================================================================
# calculate_daily_kpis
# ===================================================================
def calculate_daily_kpis(
    session: Session,
    report_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Calculate all daily KPI metrics for a given date.

    Counts are based on records created/sent during the 24-hour window
    of ``report_date`` (defaults to today UTC).

    Args:
        session: Active SQLAlchemy session.
        report_date: The date to report on (defaults to today UTC).

    Returns:
        Dict with all KPI values plus derived rates and the period label.
    """
    if report_date is None:
        report_date = datetime.now(timezone.utc)

    day_start = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    # -- Leads --
    leads_acquired = (
        session.query(func.count())
        .select_from(Lead)
        .filter(
            Lead.created_at >= day_start,
            Lead.created_at < day_end,
        )
        .scalar()
    ) or 0

    leads_enriched = (
        session.query(func.count())
        .select_from(Lead)
        .filter(
            Lead.status.in_(["enriched", "scored", "outreach", "outreach_sent",
                             "replied", "qualified", "opportunity", "escalated",
                             "won", "closed_won", "lost", "closed_lost"]),
            Lead.updated_at >= day_start,
            Lead.updated_at < day_end,
        )
        .scalar()
    ) or 0

    leads_scored = (
        session.query(func.count())
        .select_from(Lead)
        .filter(
            Lead.status.in_(["scored", "outreach", "outreach_sent", "replied",
                             "qualified", "opportunity", "escalated",
                             "won", "closed_won", "lost", "closed_lost"]),
            Lead.updated_at >= day_start,
            Lead.updated_at < day_end,
        )
        .scalar()
    ) or 0

    # -- Outreach --
    outreach_sent = (
        session.query(func.count())
        .select_from(OutreachEvent)
        .filter(
            OutreachEvent.sent_at >= day_start,
            OutreachEvent.sent_at < day_end,
            OutreachEvent.delivery_status.in_(["delivered", "sent"]),
        )
        .scalar()
    ) or 0

    bounces = (
        session.query(func.count())
        .select_from(OutreachEvent)
        .filter(
            OutreachEvent.sent_at >= day_start,
            OutreachEvent.sent_at < day_end,
            OutreachEvent.delivery_status == "bounced",
        )
        .scalar()
    ) or 0

    # -- Replies --
    replies_received = (
        session.query(func.count())
        .select_from(ReplyEvent)
        .filter(
            ReplyEvent.received_at >= day_start,
            ReplyEvent.received_at < day_end,
        )
        .scalar()
    ) or 0

    positive_replies = (
        session.query(func.count())
        .select_from(ReplyEvent)
        .filter(
            ReplyEvent.received_at >= day_start,
            ReplyEvent.received_at < day_end,
            ReplyEvent.classified_as == "positive",
        )
        .scalar()
    ) or 0

    opt_outs = (
        session.query(func.count())
        .select_from(ReplyEvent)
        .filter(
            ReplyEvent.received_at >= day_start,
            ReplyEvent.received_at < day_end,
            ReplyEvent.opt_out_flag == True,  # noqa: E712
        )
        .scalar()
    ) or 0

    # -- Opportunities --
    opportunities_created = (
        session.query(func.count())
        .select_from(Opportunity)
        .filter(
            Opportunity.status == "open",
        )
        .scalar()
    ) or 0

    # Count opportunities created today via Lead status change
    opportunities_escalated = (
        session.query(func.count())
        .select_from(Opportunity)
        .filter(
            Opportunity.escalated_at >= day_start,
            Opportunity.escalated_at < day_end,
        )
        .scalar()
    ) or 0

    # -- Nurture --
    nurture_scheduled = (
        session.query(func.count())
        .select_from(NurtureSchedule)
        .filter(
            NurtureSchedule.scheduled_at >= day_start,
            NurtureSchedule.scheduled_at < day_end,
            NurtureSchedule.cancelled == False,  # noqa: E712
        )
        .scalar()
    ) or 0

    nurture_sent = (
        session.query(func.count())
        .select_from(NurtureSchedule)
        .filter(
            NurtureSchedule.sent == True,  # noqa: E712
            NurtureSchedule.scheduled_at >= day_start,
            NurtureSchedule.scheduled_at < day_end,
        )
        .scalar()
    ) or 0

    # -- Derived Rates --
    total_outreach = outreach_sent + bounces
    reply_rate = (replies_received / total_outreach * 100) if total_outreach > 0 else 0.0
    bounce_rate = (bounces / total_outreach * 100) if total_outreach > 0 else 0.0
    opt_out_rate = (opt_outs / total_outreach * 100) if total_outreach > 0 else 0.0
    positive_rate = (positive_replies / replies_received * 100) if replies_received > 0 else 0.0

    kpis = {
        "period": day_start.strftime("%Y-%m-%d"),
        "leads_acquired": leads_acquired,
        "leads_enriched": leads_enriched,
        "leads_scored": leads_scored,
        "outreach_sent": outreach_sent,
        "replies_received": replies_received,
        "positive_replies": positive_replies,
        "opportunities_created": opportunities_created,
        "opportunities_escalated": opportunities_escalated,
        "opt_outs": opt_outs,
        "bounces": bounces,
        "nurture_scheduled": nurture_scheduled,
        "nurture_sent": nurture_sent,
        # Derived rates
        "reply_rate": round(reply_rate, 2),
        "bounce_rate": round(bounce_rate, 2),
        "opt_out_rate": round(opt_out_rate, 2),
        "positive_rate": round(positive_rate, 2),
    }

    return kpis


# ===================================================================
# build_funnel_report
# ===================================================================
def build_funnel_report(session: Session) -> Dict[str, Any]:
    """
    Build a snapshot of current leads by funnel stage.

    Groups all leads by their status and maps each status to the
    canonical funnel stage. Returns stage counts plus a total.

    Args:
        session: Active SQLAlchemy session.

    Returns:
        Dict with per-stage counts and a 'total' key.
    """
    # Get counts grouped by status
    status_counts = (
        session.query(Lead.status, func.count())
        .group_by(Lead.status)
        .all()
    )

    # Initialize all funnel stages to 0
    funnel: Dict[str, int] = {stage: 0 for stage in FUNNEL_STAGES}
    total = 0

    for status_value, count in status_counts:
        stage = STATUS_TO_FUNNEL.get(status_value, "new")
        funnel[stage] += count
        total += count

    funnel_report = {
        "stages": funnel,
        "total": total,
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
    }

    # Calculate conversion rates between adjacent stages
    conversions: Dict[str, float] = {}
    for i in range(len(FUNNEL_STAGES) - 1):
        current_stage = FUNNEL_STAGES[i]
        next_stage = FUNNEL_STAGES[i + 1]
        current_count = funnel.get(current_stage, 0)
        next_count = funnel.get(next_stage, 0)

        if current_count > 0:
            rate = round(next_count / current_count * 100, 2)
        else:
            rate = 0.0

        conversions[f"{current_stage}_to_{next_stage}"] = rate

    funnel_report["conversions"] = conversions

    return funnel_report


# ===================================================================
# check_anomalies
# ===================================================================
def check_anomalies(kpis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check KPI values against defined anomaly thresholds.

    Args:
        kpis: KPI dict from calculate_daily_kpis().

    Returns:
        List of anomaly dicts, each with 'metric', 'value', 'threshold',
        'severity', and 'message'. Empty list if all OK.
    """
    anomalies: List[Dict[str, Any]] = []

    for metric, rule in ANOMALY_THRESHOLDS.items():
        value = kpis.get(metric)
        if value is None:
            continue

        threshold = rule["threshold"]
        operator = rule["operator"]
        triggered = False

        if operator == "lt" and value < threshold:
            triggered = True
        elif operator == "gt" and value > threshold:
            triggered = True

        if triggered:
            anomalies.append({
                "metric": metric,
                "value": value,
                "threshold": threshold,
                "operator": operator,
                "severity": rule["severity"],
                "message": rule["message"],
            })

    return anomalies


# ===================================================================
# format_kpi_summary
# ===================================================================
def format_kpi_summary(kpis: Dict[str, Any]) -> str:
    """
    Format KPIs into a human-readable text summary suitable for logging
    or plain-text notifications.

    Args:
        kpis: KPI dict from calculate_daily_kpis().

    Returns:
        Multi-line formatted string.
    """
    period = kpis.get("period", "unknown")

    lines = [
        f"===== MCRcore Growth Engine - Daily KPI Report =====",
        f"Period: {period}",
        f"",
        f"--- Lead Pipeline ---",
        f"  Leads Acquired:      {kpis.get('leads_acquired', 0)}",
        f"  Leads Enriched:      {kpis.get('leads_enriched', 0)}",
        f"  Leads Scored:        {kpis.get('leads_scored', 0)}",
        f"",
        f"--- Outreach ---",
        f"  Outreach Sent:       {kpis.get('outreach_sent', 0)}",
        f"  Bounces:             {kpis.get('bounces', 0)}",
        f"  Bounce Rate:         {kpis.get('bounce_rate', 0)}%",
        f"",
        f"--- Replies ---",
        f"  Replies Received:    {kpis.get('replies_received', 0)}",
        f"  Positive Replies:    {kpis.get('positive_replies', 0)}",
        f"  Reply Rate:          {kpis.get('reply_rate', 0)}%",
        f"  Positive Rate:       {kpis.get('positive_rate', 0)}%",
        f"  Opt-Outs:            {kpis.get('opt_outs', 0)}",
        f"  Opt-Out Rate:        {kpis.get('opt_out_rate', 0)}%",
        f"",
        f"--- Opportunities ---",
        f"  Open Opportunities:  {kpis.get('opportunities_created', 0)}",
        f"  Escalated Today:     {kpis.get('opportunities_escalated', 0)}",
        f"",
        f"--- Nurture ---",
        f"  Nurture Scheduled:   {kpis.get('nurture_scheduled', 0)}",
        f"  Nurture Sent:        {kpis.get('nurture_sent', 0)}",
        f"",
    ]

    # Append anomaly warnings
    anomalies = check_anomalies(kpis)
    if anomalies:
        lines.append("--- ANOMALIES DETECTED ---")
        for anomaly in anomalies:
            severity_icon = "🚨" if anomaly["severity"] == "alert" else "⚠️"
            lines.append(
                f"  {severity_icon} {anomaly['metric']}: "
                f"{anomaly['value']}% (threshold: {anomaly['operator']} "
                f"{anomaly['threshold']}%) — {anomaly['message']}"
            )
        lines.append("")

    lines.append("=" * 52)
    return "\n".join(lines)


# ===================================================================
# format_teams_kpi_card
# ===================================================================
def format_teams_kpi_card(kpis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format KPIs into the dict structure expected by
    ``src.utils.teams_notifier.send_daily_kpi()``.

    Maps internal KPI keys to the label format used by the Teams card.

    Args:
        kpis: KPI dict from calculate_daily_kpis().

    Returns:
        Dict ready to pass to ``send_daily_kpi(kpi_data=...)``.
    """
    anomalies = check_anomalies(kpis)
    anomaly_text = ""
    if anomalies:
        parts = []
        for a in anomalies:
            severity_icon = "🚨" if a["severity"] == "alert" else "⚠️"
            parts.append(f"{severity_icon} {a['message']}")
        anomaly_text = " | ".join(parts)

    card_data = {
        "period": kpis.get("period", "unknown"),
        "leads_generated": kpis.get("leads_acquired", 0),
        "emails_sent": kpis.get("outreach_sent", 0),
        "replies_received": kpis.get("replies_received", 0),
        "positive_replies": kpis.get("positive_replies", 0),
        "meetings_booked": kpis.get("opportunities_escalated", 0),
        "pipeline_value": f"{kpis.get('opportunities_created', 0)} open",
        "conversion_rate": f"{kpis.get('positive_rate', 0)}%",
        "bounce_rate": f"{kpis.get('bounce_rate', 0)}%",
        "opt_out_rate": f"{kpis.get('opt_out_rate', 0)}%",
        "reply_rate": f"{kpis.get('reply_rate', 0)}%",
        "nurture_sent": kpis.get("nurture_sent", 0),
    }

    if anomaly_text:
        card_data["anomalies"] = anomaly_text

    return card_data
