"""
MCRcore Growth Engine - Compliance Check Skill

CAN-SPAM compliance definitions, validation rules, required footer templates,
suppression rules, sender-auth check definitions, and unsubscribe text options.

All outbound email must pass every check defined here before sending.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# =========================================================================
# Physical address (CAN-SPAM requirement)
# =========================================================================
PHYSICAL_ADDRESS = "136 W. Official Road, Addison, IL 60101"

# =========================================================================
# CAN-SPAM Checklist
# =========================================================================
CAN_SPAM_CHECKLIST = [
    "suppression_check",       # Email not on suppression list
    "opt_out_check",           # Recipient has not opted out
    "source_approval_check",   # Lead source is approved for outreach
    "contact_validity_check",  # Valid email format, not bounced
    "sender_identity_check",   # From address matches configured sender
    "subject_line_check",      # Truthful, non-deceptive subject
    "footer_check",            # Contains physical mailing address
    "unsubscribe_check",       # Contains unsubscribe mechanism
    "domain_auth_check",       # SPF/DKIM/DMARC configured
]

# =========================================================================
# Required Footer Templates
# =========================================================================
FOOTER_TEMPLATES = {
    "standard": (
        "MCR Consulting Group | {address}\n"
        "You are receiving this email because you were identified as a potential "
        "fit for our managed IT and consulting services.\n"
        "To unsubscribe, reply with 'UNSUBSCRIBE' or click the link below."
    ),
    "minimal": (
        "MCR Consulting Group, {address}\n"
        "Unsubscribe: Reply 'UNSUBSCRIBE' to opt out of future messages."
    ),
    "nurture": (
        "MCR Consulting Group | {address}\n"
        "You are receiving this as part of an informational series.\n"
        "To stop receiving these messages, reply 'UNSUBSCRIBE' or click below."
    ),
}

# Pre-fill address in templates
FOOTER_TEMPLATES_RENDERED = {
    k: v.format(address=PHYSICAL_ADDRESS) for k, v in FOOTER_TEMPLATES.items()
}

# =========================================================================
# Suppression Rules
# =========================================================================
SUPPRESSION_REASONS = {
    "hard_bounce":   "Email address returned a hard bounce (permanent failure).",
    "soft_bounce_3": "Email address returned 3+ soft bounces within 30 days.",
    "opt_out":       "Recipient explicitly opted out / unsubscribed.",
    "complaint":     "Recipient filed a spam complaint.",
    "manual":        "Manually added by an administrator.",
    "role_address":  "Role-based address (e.g. info@, support@) excluded by policy.",
    "legal_request": "Suppressed due to a legal or regulatory request.",
}

# Role-based prefixes that should be auto-suppressed
ROLE_ADDRESS_PREFIXES = [
    "info@", "support@", "admin@", "sales@", "contact@",
    "help@", "noreply@", "no-reply@", "abuse@", "postmaster@",
    "webmaster@", "billing@", "legal@", "compliance@",
]

# =========================================================================
# Sender Identity - Allowed From Addresses
# =========================================================================
APPROVED_SENDER_DOMAINS = [
    "mcrconsultinggroup.com",
    "mcr-consulting.com",
]

APPROVED_SENDER_ADDRESSES = [
    "outreach@mcrconsultinggroup.com",
    "hello@mcrconsultinggroup.com",
    "partnerships@mcrconsultinggroup.com",
]

# =========================================================================
# Subject Line Validation Rules
# =========================================================================

# Maximum subject length
MAX_SUBJECT_LENGTH = 150

# Minimum subject length (too short = suspicious)
MIN_SUBJECT_LENGTH = 3

# Misleading prefixes (CAN-SPAM: subject cannot be deceptive)
MISLEADING_PREFIXES = [
    r"^RE:\s",       # Fake reply
    r"^FW:\s",       # Fake forward
    r"^FWD:\s",      # Fake forward variant
    r"^Re:\s",       # Fake reply (title case)
    r"^Fw:\s",       # Fake forward (title case)
    r"^Fwd:\s",      # Fake forward variant (title case)
]
MISLEADING_PREFIX_PATTERNS = [re.compile(p) for p in MISLEADING_PREFIXES]

# ALL CAPS threshold: if >60% uppercase letters, flag it
ALL_CAPS_THRESHOLD = 0.60

# Excessive punctuation patterns
EXCESSIVE_PUNCTUATION_PATTERNS = [
    re.compile(r"[!]{2,}"),      # Multiple exclamation marks
    re.compile(r"[?]{2,}"),      # Multiple question marks
    re.compile(r"[$]{2,}"),      # Multiple dollar signs
    re.compile(r"[!?]{3,}"),     # Mixed excessive punctuation
    re.compile(r"\.{4,}"),       # Excessive ellipsis
]

# Spam-trigger words in subject (basic set)
SPAM_TRIGGER_WORDS = [
    "act now", "limited time", "free money", "winner", "congratulations",
    "urgent", "click here", "buy now", "order now", "no obligation",
    "risk free", "100% free", "double your", "earn extra cash",
]
SPAM_TRIGGER_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in SPAM_TRIGGER_WORDS) + r")\b",
    re.IGNORECASE,
)


def validate_subject_line(subject: str) -> Tuple[bool, List[str]]:
    """
    Validate a subject line against CAN-SPAM and deliverability rules.

    Returns:
        (passed, issues) - True if valid, list of issue descriptions.
    """
    issues: List[str] = []

    if not subject or not subject.strip():
        issues.append("Subject line is empty.")
        return False, issues

    subject = subject.strip()

    # Length checks
    if len(subject) < MIN_SUBJECT_LENGTH:
        issues.append(f"Subject too short ({len(subject)} chars, min {MIN_SUBJECT_LENGTH}).")
    if len(subject) > MAX_SUBJECT_LENGTH:
        issues.append(f"Subject too long ({len(subject)} chars, max {MAX_SUBJECT_LENGTH}).")

    # Misleading prefix check
    for pattern in MISLEADING_PREFIX_PATTERNS:
        if pattern.match(subject):
            issues.append(
                f"Subject contains misleading prefix '{subject.split()[0]}' "
                "implying a prior conversation that does not exist."
            )
            break

    # ALL CAPS check
    alpha_chars = [c for c in subject if c.isalpha()]
    if alpha_chars:
        upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if upper_ratio > ALL_CAPS_THRESHOLD:
            issues.append(
                f"Subject is {upper_ratio:.0%} uppercase. "
                "Excessive capitalization triggers spam filters."
            )

    # Excessive punctuation
    for pattern in EXCESSIVE_PUNCTUATION_PATTERNS:
        if pattern.search(subject):
            issues.append("Subject contains excessive punctuation.")
            break

    # Spam trigger words
    match = SPAM_TRIGGER_PATTERN.search(subject)
    if match:
        issues.append(f"Subject contains spam-trigger phrase: '{match.group()}'.")

    passed = len(issues) == 0
    return passed, issues


# =========================================================================
# Unsubscribe Text Options
# =========================================================================
UNSUBSCRIBE_TEXTS = [
    "unsubscribe",
    "opt out",
    "opt-out",
    "stop receiving",
    "remove me",
    "no longer wish to receive",
    "manage your preferences",
    "email preferences",
    "update subscription",
]

UNSUBSCRIBE_LINK_PATTERNS = [
    re.compile(r"https?://[^\s]+unsubscribe[^\s]*", re.IGNORECASE),
    re.compile(r"https?://[^\s]+opt[_-]?out[^\s]*", re.IGNORECASE),
    re.compile(r"https?://[^\s]+preferences[^\s]*", re.IGNORECASE),
]


def body_has_unsubscribe(body: str) -> Tuple[bool, str]:
    """
    Check whether the email body contains an unsubscribe mechanism.

    Returns:
        (found, mechanism_description)
    """
    if not body:
        return False, "Email body is empty."

    body_lower = body.lower()

    # Check for unsubscribe text
    for text in UNSUBSCRIBE_TEXTS:
        if text in body_lower:
            return True, f"Found unsubscribe text: '{text}'"

    # Check for unsubscribe links
    for pattern in UNSUBSCRIBE_LINK_PATTERNS:
        if pattern.search(body):
            return True, "Found unsubscribe link in body."

    return False, "No unsubscribe mechanism found in email body."


def body_has_physical_address(body: str) -> Tuple[bool, str]:
    """
    Check whether the email body contains the required physical address.

    Returns:
        (found, detail)
    """
    if not body:
        return False, "Email body is empty."

    # Check for the exact address
    if PHYSICAL_ADDRESS in body:
        return True, f"Found physical address: {PHYSICAL_ADDRESS}"

    # Check for partial address components (flexible matching)
    addr_parts = ["136", "Official", "Addison", "IL", "60101"]
    matches = sum(1 for part in addr_parts if part in body)
    if matches >= 4:
        return True, "Found partial physical address match (4+ components)."

    return False, f"Required physical address not found: {PHYSICAL_ADDRESS}"


# =========================================================================
# Domain Auth Definitions (SPF/DKIM/DMARC)
# =========================================================================
@dataclass
class DomainAuthConfig:
    """Configuration for domain authentication checks."""
    domain: str
    spf_expected: bool = True
    dkim_expected: bool = True
    dmarc_expected: bool = True
    dmarc_policy: str = "reject"  # none / quarantine / reject


DOMAIN_AUTH_CONFIGS: Dict[str, DomainAuthConfig] = {
    "mcrconsultinggroup.com": DomainAuthConfig(
        domain="mcrconsultinggroup.com",
        spf_expected=True,
        dkim_expected=True,
        dmarc_expected=True,
        dmarc_policy="reject",
    ),
    "mcr-consulting.com": DomainAuthConfig(
        domain="mcr-consulting.com",
        spf_expected=True,
        dkim_expected=True,
        dmarc_expected=True,
        dmarc_policy="quarantine",
    ),
}
