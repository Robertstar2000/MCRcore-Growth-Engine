"""
MCRcore Growth Engine - SMTP Email Sender

Sends individual and bulk emails via SMTP with rate limiting.
Configure via environment variables:
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
    SMTP_USE_TLS, SMTP_FROM_ADDRESS, SMTP_RATE_LIMIT_PER_MINUTE
"""

import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional

from dotenv import load_dotenv

from src.utils.logger import setup_logger

load_dotenv()

logger = setup_logger("mcr_growth_engine.email_sender")

# SMTP configuration
SMTP_HOST = os.getenv("SMTP_HOST", "PLACEHOLDER_smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "PLACEHOLDER_your-smtp-username")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "PLACEHOLDER_your-smtp-password")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
SMTP_FROM_ADDRESS = os.getenv("SMTP_FROM_ADDRESS", "PLACEHOLDER_growth-engine@example.com")
SMTP_RATE_LIMIT = int(os.getenv("SMTP_RATE_LIMIT_PER_MINUTE", "30"))


class RateLimiter:
    """Simple token-bucket rate limiter for email sending."""

    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.interval = 60.0 / max_per_minute if max_per_minute > 0 else 0
        self._last_send_time = 0.0
        self._count_this_minute = 0
        self._minute_start = 0.0

    def wait_if_needed(self):
        """Block until we're allowed to send the next email."""
        now = time.time()

        # Reset counter each minute
        if now - self._minute_start >= 60.0:
            self._count_this_minute = 0
            self._minute_start = now

        if self._count_this_minute >= self.max_per_minute:
            sleep_time = 60.0 - (now - self._minute_start)
            if sleep_time > 0:
                logger.info(f"Rate limit reached, sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
            self._count_this_minute = 0
            self._minute_start = time.time()

        # Minimum interval between sends
        elapsed = now - self._last_send_time
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)

        self._last_send_time = time.time()
        self._count_this_minute += 1


# Module-level rate limiter
_rate_limiter = RateLimiter(SMTP_RATE_LIMIT)


def _is_configured() -> bool:
    """Check whether SMTP settings have been filled in."""
    return "PLACEHOLDER" not in SMTP_HOST and "PLACEHOLDER" not in SMTP_USERNAME


def _create_smtp_connection() -> smtplib.SMTP:
    """Create and authenticate an SMTP connection."""
    if SMTP_USE_TLS:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
    else:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)

    server.login(SMTP_USERNAME, SMTP_PASSWORD)
    return server


def send_email(
    to: str,
    subject: str,
    body: str,
    from_addr: str = None,
    reply_to: str = None,
    html: bool = False,
) -> bool:
    """
    Send a single email via SMTP.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body (plain text or HTML).
        from_addr: Sender address override. Defaults to SMTP_FROM_ADDRESS.
        reply_to: Reply-To header address.
        html: If True, send body as HTML.

    Returns:
        True if email was sent successfully.
    """
    if not _is_configured():
        logger.warning("SMTP not configured (PLACEHOLDER values) - skipping send")
        return False

    from_addr = from_addr or SMTP_FROM_ADDRESS

    msg = MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to

    content_type = "html" if html else "plain"
    msg.attach(MIMEText(body, content_type, "utf-8"))

    _rate_limiter.wait_if_needed()

    try:
        server = _create_smtp_connection()
        server.sendmail(from_addr, [to], msg.as_string())
        server.quit()
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending to {to}: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


def send_bulk(
    recipients_list: List[Dict[str, str]],
    from_addr: str = None,
    reply_to: str = None,
) -> Dict[str, bool]:
    """
    Send emails to a list of recipients with rate limiting.

    Args:
        recipients_list: List of dicts, each with keys:
            - to: Recipient email
            - subject: Email subject
            - body: Email body
            - html (optional): If "true", send as HTML
        from_addr: Sender address override.
        reply_to: Reply-To header.

    Returns:
        Dict mapping recipient email to send success (True/False).
    """
    if not _is_configured():
        logger.warning("SMTP not configured - skipping bulk send")
        return {r.get("to", "unknown"): False for r in recipients_list}

    results = {}
    total = len(recipients_list)

    logger.info(f"Starting bulk send to {total} recipients (rate limit: {SMTP_RATE_LIMIT}/min)")

    for i, recipient in enumerate(recipients_list, 1):
        to = recipient.get("to", "")
        subject = recipient.get("subject", "")
        body = recipient.get("body", "")
        is_html = recipient.get("html", "false").lower() == "true"

        success = send_email(
            to=to,
            subject=subject,
            body=body,
            from_addr=from_addr,
            reply_to=reply_to,
            html=is_html,
        )
        results[to] = success

        if i % 10 == 0:
            logger.info(f"Bulk send progress: {i}/{total}")

    sent = sum(1 for v in results.values() if v)
    logger.info(f"Bulk send complete: {sent}/{total} successful")
    return results
