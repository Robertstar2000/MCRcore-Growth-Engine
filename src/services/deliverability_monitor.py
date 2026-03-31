"""
MCRcore Growth Engine - Deliverability Monitoring Service

Tracks bounces, complaints, and overall sending health.  Implements a
kill-switch that pauses all sending when thresholds are exceeded:

    - Bounce rate  > 5%    -> PAUSE + Teams alert
    - Complaint rate > 0.1% -> PAUSE + Teams alert

Also provides volume throttling for new / warming sending domains.
"""

import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.utils.logger import setup_logger
from src.utils.teams_notifier import send_teams_card, send_teams_message

logger = setup_logger("mcr_growth_engine.deliverability_monitor")

# -----------------------------------------------------------------------
# Thresholds
# -----------------------------------------------------------------------
BOUNCE_RATE_THRESHOLD = 0.05       # 5 %
COMPLAINT_RATE_THRESHOLD = 0.001   # 0.1 %

# -----------------------------------------------------------------------
# Throttling defaults for new domains
# -----------------------------------------------------------------------
DEFAULT_DAILY_LIMIT_NEW_DOMAIN = 50
DAILY_LIMIT_RAMP_SCHEDULE = {
    # day offset from first send -> daily limit
    0: 50,
    7: 100,
    14: 200,
    21: 400,
    30: 800,
    45: 1500,
    60: 3000,
}


class DeliverabilityMonitor:
    """
    Monitors email deliverability metrics and enforces send-safety.

    Parameters
    ----------
    db_session : optional
        SQLAlchemy session for persistence.  When None, an in-memory
        store is used.
    """

    def __init__(self, db_session=None):
        self._session = db_session
        self._audit_log: List[dict] = []

        # In-memory event stores
        self._bounces: List[dict] = []
        self._complaints: List[dict] = []
        self._sends: List[dict] = []

        # Kill-switch state
        self._sending_paused: bool = False
        self._pause_reason: Optional[str] = None
        self._pause_timestamp: Optional[str] = None

        # Domain warming tracker: domain -> first_send_date
        self._domain_first_send: Dict[str, datetime] = {}
        self._domain_send_counts_today: Dict[str, int] = defaultdict(int)
        self._domain_count_date: Optional[str] = None  # YYYY-MM-DD

    # ------------------------------------------------------------------
    # Recording events
    # ------------------------------------------------------------------

    def record_send(self, email: str, domain: str = None) -> dict:
        """Record an outbound send for rate calculations."""
        now = datetime.now(timezone.utc)
        event = {
            "event_id": str(uuid.uuid4()),
            "email": email.strip().lower(),
            "domain": domain or email.split("@")[-1],
            "timestamp": now.isoformat(),
            "type": "send",
        }
        self._sends.append(event)

        # Domain warming tracking
        d = event["domain"]
        if d not in self._domain_first_send:
            self._domain_first_send[d] = now

        today_str = now.strftime("%Y-%m-%d")
        if self._domain_count_date != today_str:
            self._domain_send_counts_today.clear()
            self._domain_count_date = today_str
        self._domain_send_counts_today[d] += 1

        return event

    def record_bounce(self, email: str, bounce_type: str = "hard") -> dict:
        """
        Record an email bounce.

        Args:
            email:       The bounced email address.
            bounce_type: 'hard' or 'soft'.

        Returns:
            Bounce event dict.
        """
        now = datetime.now(timezone.utc)
        event = {
            "event_id": str(uuid.uuid4()),
            "email": email.strip().lower(),
            "bounce_type": bounce_type,
            "timestamp": now.isoformat(),
        }
        self._bounces.append(event)
        logger.warning(f"Bounce recorded: {email} type={bounce_type}")

        self._log_audit("bounce_recorded", email, after=event)

        # Auto-check thresholds after recording
        self._auto_check()

        return event

    def record_complaint(self, email: str) -> dict:
        """
        Record a spam complaint.

        Args:
            email: The complaining recipient's address.

        Returns:
            Complaint event dict.
        """
        now = datetime.now(timezone.utc)
        event = {
            "event_id": str(uuid.uuid4()),
            "email": email.strip().lower(),
            "timestamp": now.isoformat(),
        }
        self._complaints.append(event)
        logger.warning(f"Complaint recorded: {email}")

        self._log_audit("complaint_recorded", email, after=event)

        # Auto-check thresholds after recording
        self._auto_check()

        return event

    # ------------------------------------------------------------------
    # Rate calculations
    # ------------------------------------------------------------------

    def check_bounce_rate(self, timeframe_hours: int = 24) -> Dict[str, Any]:
        """
        Calculate the bounce rate within the given timeframe.

        Returns:
            Dict with total_sends, total_bounces, bounce_rate, threshold,
            exceeded.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=timeframe_hours)
        cutoff_iso = cutoff.isoformat()

        sends_in_window = [
            s for s in self._sends if s["timestamp"] >= cutoff_iso
        ]
        bounces_in_window = [
            b for b in self._bounces if b["timestamp"] >= cutoff_iso
        ]

        total_sends = len(sends_in_window)
        total_bounces = len(bounces_in_window)
        rate = (total_bounces / total_sends) if total_sends > 0 else 0.0

        return {
            "timeframe_hours": timeframe_hours,
            "total_sends": total_sends,
            "total_bounces": total_bounces,
            "bounce_rate": round(rate, 6),
            "threshold": BOUNCE_RATE_THRESHOLD,
            "exceeded": rate > BOUNCE_RATE_THRESHOLD,
        }

    def check_complaint_rate(self, timeframe_hours: int = 24) -> Dict[str, Any]:
        """
        Calculate the complaint rate within the given timeframe.

        Returns:
            Dict with total_sends, total_complaints, complaint_rate,
            threshold, exceeded.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=timeframe_hours)
        cutoff_iso = cutoff.isoformat()

        sends_in_window = [
            s for s in self._sends if s["timestamp"] >= cutoff_iso
        ]
        complaints_in_window = [
            c for c in self._complaints if c["timestamp"] >= cutoff_iso
        ]

        total_sends = len(sends_in_window)
        total_complaints = len(complaints_in_window)
        rate = (total_complaints / total_sends) if total_sends > 0 else 0.0

        return {
            "timeframe_hours": timeframe_hours,
            "total_sends": total_sends,
            "total_complaints": total_complaints,
            "complaint_rate": round(rate, 6),
            "threshold": COMPLAINT_RATE_THRESHOLD,
            "exceeded": rate > COMPLAINT_RATE_THRESHOLD,
        }

    # ------------------------------------------------------------------
    # Kill-switch
    # ------------------------------------------------------------------

    def should_pause_sending(self) -> bool:
        """
        Check whether sending should be paused.

        Evaluates bounce and complaint rates.  If thresholds are exceeded,
        pauses sending and fires a Teams alert.

        Returns:
            True if sending is paused (or should be paused).
        """
        if self._sending_paused:
            return True

        bounce_info = self.check_bounce_rate()
        complaint_info = self.check_complaint_rate()

        reasons: List[str] = []
        if bounce_info["exceeded"]:
            reasons.append(
                f"Bounce rate {bounce_info['bounce_rate']:.2%} exceeds "
                f"threshold {BOUNCE_RATE_THRESHOLD:.2%}"
            )
        if complaint_info["exceeded"]:
            reasons.append(
                f"Complaint rate {complaint_info['complaint_rate']:.4%} exceeds "
                f"threshold {COMPLAINT_RATE_THRESHOLD:.4%}"
            )

        if reasons:
            self._activate_kill_switch(reasons)
            return True

        return False

    def resume_sending(self, admin_actor: str) -> dict:
        """
        Resume sending after a pause.  Should only be called after
        investigation.

        Args:
            admin_actor: Who is authorising the resume.

        Returns:
            Status dict.
        """
        was_paused = self._sending_paused
        self._sending_paused = False
        prev_reason = self._pause_reason
        self._pause_reason = None
        self._pause_timestamp = None

        logger.info(f"Sending resumed by {admin_actor}")
        self._log_audit(
            "sending_resumed", "system",
            before={"paused": was_paused, "reason": prev_reason},
            after={"resumed_by": admin_actor},
            actor=admin_actor,
        )

        send_teams_message(
            f"✅ Email sending RESUMED by {admin_actor}. "
            f"Previous pause reason: {prev_reason}"
        )

        return {
            "sending_paused": False,
            "resumed_by": admin_actor,
            "previous_reason": prev_reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _activate_kill_switch(self, reasons: List[str]):
        """Activate the kill switch and alert via Teams."""
        self._sending_paused = True
        self._pause_reason = "; ".join(reasons)
        self._pause_timestamp = datetime.now(timezone.utc).isoformat()

        logger.critical(f"KILL SWITCH ACTIVATED: {self._pause_reason}")

        self._log_audit(
            "kill_switch_activated", "system",
            after={"reasons": reasons, "paused_at": self._pause_timestamp},
        )

        # Teams alert
        send_teams_card(
            title="🚨 EMAIL SENDING PAUSED - Kill Switch Activated",
            facts=[
                {"title": "Reason", "value": self._pause_reason},
                {"title": "Paused At", "value": self._pause_timestamp},
                {"title": "Action Required", "value": "Investigate and call resume_sending()"},
            ],
        )

    # ------------------------------------------------------------------
    # Throttling
    # ------------------------------------------------------------------

    def get_daily_limit(self, domain: str) -> int:
        """
        Get the current daily send limit for a domain based on its
        warming schedule.

        Args:
            domain: Sending domain.

        Returns:
            Maximum emails allowed today for this domain.
        """
        first_send = self._domain_first_send.get(domain)
        if first_send is None:
            return DEFAULT_DAILY_LIMIT_NEW_DOMAIN

        days_active = (datetime.now(timezone.utc) - first_send).days

        # Walk the ramp schedule
        limit = DEFAULT_DAILY_LIMIT_NEW_DOMAIN
        for day_offset in sorted(DAILY_LIMIT_RAMP_SCHEDULE.keys()):
            if days_active >= day_offset:
                limit = DAILY_LIMIT_RAMP_SCHEDULE[day_offset]

        return limit

    def can_send_for_domain(self, domain: str) -> Tuple[bool, str]:
        """
        Check whether another email can be sent from this domain today.

        Returns:
            (allowed, reason)
        """
        if self._sending_paused:
            return False, f"Sending is paused: {self._pause_reason}"

        limit = self.get_daily_limit(domain)

        # Reset daily counter if date rolled over
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._domain_count_date != today_str:
            self._domain_send_counts_today.clear()
            self._domain_count_date = today_str

        current = self._domain_send_counts_today.get(domain, 0)
        if current >= limit:
            return False, (
                f"Daily limit reached for {domain}: "
                f"{current}/{limit} (warming ramp)"
            )

        return True, f"OK ({current}/{limit} sent today)"

    # ------------------------------------------------------------------
    # Health report
    # ------------------------------------------------------------------

    def get_health_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive deliverability health report.

        Returns:
            Dict with bounce rates, complaint rates, domain stats,
            pause status, and recommendations.
        """
        bounce_24h = self.check_bounce_rate(24)
        bounce_7d = self.check_bounce_rate(168)
        complaint_24h = self.check_complaint_rate(24)
        complaint_7d = self.check_complaint_rate(168)

        # Per-domain breakdown
        domain_stats: Dict[str, dict] = {}
        for send in self._sends:
            d = send.get("domain", "unknown")
            if d not in domain_stats:
                domain_stats[d] = {
                    "sends": 0,
                    "bounces": 0,
                    "complaints": 0,
                    "daily_limit": self.get_daily_limit(d),
                    "sent_today": self._domain_send_counts_today.get(d, 0),
                }
            domain_stats[d]["sends"] += 1

        for bounce in self._bounces:
            d = bounce.get("email", "@unknown").split("@")[-1]
            if d in domain_stats:
                domain_stats[d]["bounces"] += 1

        for complaint in self._complaints:
            d = complaint.get("email", "@unknown").split("@")[-1]
            if d in domain_stats:
                domain_stats[d]["complaints"] += 1

        # Recommendations
        recommendations: List[str] = []
        if bounce_24h["exceeded"]:
            recommendations.append(
                "CRITICAL: 24h bounce rate exceeds threshold. "
                "Clean your list and investigate bounced addresses."
            )
        if complaint_24h["exceeded"]:
            recommendations.append(
                "CRITICAL: 24h complaint rate exceeds threshold. "
                "Review targeting and content immediately."
            )
        if bounce_7d["bounce_rate"] > 0.03:
            recommendations.append(
                "WARNING: 7-day bounce rate is elevated (>3%). "
                "Consider tightening email validation."
            )
        if not recommendations:
            recommendations.append("All deliverability metrics are within safe limits.")

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sending_paused": self._sending_paused,
            "pause_reason": self._pause_reason,
            "bounce_rate_24h": bounce_24h,
            "bounce_rate_7d": bounce_7d,
            "complaint_rate_24h": complaint_24h,
            "complaint_rate_7d": complaint_7d,
            "total_sends": len(self._sends),
            "total_bounces": len(self._bounces),
            "total_complaints": len(self._complaints),
            "domain_stats": domain_stats,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Auto-check (called after each bounce / complaint)
    # ------------------------------------------------------------------

    def _auto_check(self):
        """Run should_pause_sending after every event."""
        self.should_pause_sending()

    # ------------------------------------------------------------------
    # Audit helper
    # ------------------------------------------------------------------

    def _log_audit(
        self,
        action: str,
        entity_id: str,
        before: dict = None,
        after: dict = None,
        actor: str = "deliverability_monitor",
    ):
        entry = {
            "audit_id": str(uuid.uuid4()),
            "actor": actor,
            "entity_type": "deliverability",
            "entity_id": entity_id,
            "action": action,
            "before": before,
            "after": after,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._audit_log.append(entry)

    def get_audit_log(self) -> List[dict]:
        return list(self._audit_log)
