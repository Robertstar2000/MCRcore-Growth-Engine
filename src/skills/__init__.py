# MCRcore Growth Engine - Skills Package
from src.skills.compliance_check import (
    CAN_SPAM_CHECKLIST,
    PHYSICAL_ADDRESS,
    validate_subject_line,
    body_has_unsubscribe,
    body_has_physical_address,
)
from src.skills.icp_targeting import score_icp_fit
from src.skills.lead_scoring import compute_weighted_score
from src.skills.erp_signal_detection import detect_erp_signals
from src.skills.offer_matching import match_offer
from src.skills.reply_intent import classify_reply_intent
from src.skills.nurture_cadence import (
    get_next_nurture_stage,
    calculate_schedule_time,
    should_cancel_nurture,
)
from src.skills.analytics_reporting import (
    calculate_daily_kpis,
    check_anomalies,
    format_kpi_summary,
)

__all__ = [
    "CAN_SPAM_CHECKLIST",
    "PHYSICAL_ADDRESS",
    "validate_subject_line",
    "body_has_unsubscribe",
    "body_has_physical_address",
    "score_icp_fit",
    "compute_weighted_score",
    "detect_erp_signals",
    "match_offer",
    "classify_reply_intent",
    "get_next_nurture_stage",
    "calculate_schedule_time",
    "should_cancel_nurture",
    "calculate_daily_kpis",
    "check_anomalies",
    "format_kpi_summary",
]
