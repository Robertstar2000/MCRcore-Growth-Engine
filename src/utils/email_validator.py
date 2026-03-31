"""
MCRcore Growth Engine - Email Validation Utilities

Provides format validation, MX record checking, and bounce risk estimation.
"""

import re
from typing import Tuple

from src.utils.logger import setup_logger

logger = setup_logger("mcr_growth_engine.email_validator")

# Common disposable / temporary email domains
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "yopmail.com", "sharklasers.com", "guerrillamailblock.com", "grr.la",
    "dispostable.com", "trashmail.com", "10minutemail.com", "temp-mail.org",
}

# Common free email providers (higher bounce risk for B2B)
FREE_PROVIDERS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "mail.com", "protonmail.com", "zoho.com", "yandex.com",
}

# RFC 5322 simplified email regex
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$"
)


def validate_email_format(email: str) -> bool:
    """
    Check whether an email address has a valid format.

    Args:
        email: Email address string.

    Returns:
        True if format is valid.
    """
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def check_mx_record(domain: str) -> bool:
    """
    Check whether the domain has valid MX records.

    Uses dnspython for DNS lookups. Returns True if at least one MX record
    exists, False otherwise.

    Args:
        domain: Email domain to check (e.g. 'example.com').

    Returns:
        True if MX records found.
    """
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "MX")
        has_mx = len(answers) > 0
        logger.debug(f"MX check for {domain}: {'found' if has_mx else 'none'}")
        return has_mx
    except ImportError:
        logger.warning("dnspython not installed; skipping MX check")
        return True  # Assume valid if we can't check
    except Exception as e:
        logger.debug(f"MX check failed for {domain}: {e}")
        return False


def estimate_bounce_risk(email: str) -> Tuple[str, float]:
    """
    Estimate the bounce risk for an email address.

    Risk levels:
        - "low"    (0.0-0.3): Valid format, corporate domain with MX
        - "medium" (0.3-0.6): Free provider or missing MX
        - "high"   (0.6-1.0): Disposable domain, invalid format

    Args:
        email: Email address to assess.

    Returns:
        Tuple of (risk_level: str, risk_score: float).
    """
    if not validate_email_format(email):
        logger.info(f"Bounce risk HIGH - invalid format: {email}")
        return ("high", 1.0)

    email = email.strip().lower()
    domain = email.split("@")[1]

    # Disposable domains -> high risk
    if domain in DISPOSABLE_DOMAINS:
        logger.info(f"Bounce risk HIGH - disposable domain: {domain}")
        return ("high", 0.9)

    # Check MX records
    has_mx = check_mx_record(domain)

    if not has_mx:
        logger.info(f"Bounce risk HIGH - no MX records: {domain}")
        return ("high", 0.8)

    # Free providers -> medium risk for B2B outreach
    if domain in FREE_PROVIDERS:
        logger.info(f"Bounce risk MEDIUM - free provider: {domain}")
        return ("medium", 0.4)

    # Corporate domain with MX -> low risk
    logger.info(f"Bounce risk LOW - corporate domain: {domain}")
    return ("low", 0.1)


def validate_email(email: str) -> dict:
    """
    Full email validation returning a comprehensive result dict.

    Args:
        email: Email address to validate.

    Returns:
        Dict with keys: email, valid_format, domain, has_mx,
        risk_level, risk_score, is_disposable, is_free_provider.
    """
    email_clean = (email or "").strip().lower()
    valid_format = validate_email_format(email_clean)

    if not valid_format:
        return {
            "email": email_clean,
            "valid_format": False,
            "domain": None,
            "has_mx": False,
            "risk_level": "high",
            "risk_score": 1.0,
            "is_disposable": False,
            "is_free_provider": False,
        }

    domain = email_clean.split("@")[1]
    has_mx = check_mx_record(domain)
    risk_level, risk_score = estimate_bounce_risk(email_clean)

    return {
        "email": email_clean,
        "valid_format": True,
        "domain": domain,
        "has_mx": has_mx,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "is_disposable": domain in DISPOSABLE_DOMAINS,
        "is_free_provider": domain in FREE_PROVIDERS,
    }
