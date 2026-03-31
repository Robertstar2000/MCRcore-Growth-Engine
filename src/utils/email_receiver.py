"""
MCRcore Growth Engine - IMAP Email Receiver

Checks inboxes for new replies and parses email threads.
Configure via environment variables:
    IMAP_HOST, IMAP_PORT, IMAP_USERNAME, IMAP_PASSWORD,
    IMAP_USE_SSL, IMAP_FOLDER
"""

import email
import os
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from typing import Dict, List, Optional

from dotenv import load_dotenv

from src.utils.logger import setup_logger

load_dotenv()

logger = setup_logger("mcr_growth_engine.email_receiver")

# IMAP configuration
IMAP_HOST = os.getenv("IMAP_HOST", "PLACEHOLDER_imap.example.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USERNAME = os.getenv("IMAP_USERNAME", "PLACEHOLDER_your-imap-username")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "PLACEHOLDER_your-imap-password")
IMAP_USE_SSL = os.getenv("IMAP_USE_SSL", "true").lower() == "true"
IMAP_FOLDER = os.getenv("IMAP_FOLDER", "INBOX")


def _is_configured() -> bool:
    """Check whether IMAP settings have been filled in."""
    return "PLACEHOLDER" not in IMAP_HOST and "PLACEHOLDER" not in IMAP_USERNAME


def _get_imap_client():
    """Create and authenticate an IMAP client connection."""
    try:
        from imapclient import IMAPClient
    except ImportError:
        logger.error("imapclient not installed. Run: pip install imapclient")
        raise

    client = IMAPClient(IMAP_HOST, port=IMAP_PORT, ssl=IMAP_USE_SSL)
    client.login(IMAP_USERNAME, IMAP_PASSWORD)
    return client


def _decode_header_value(value) -> str:
    """Decode an email header into a plain string."""
    if value is None:
        return ""
    decoded_parts = decode_header(str(value))
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)


def _extract_body(msg) -> str:
    """Extract the plain-text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # Fallback: try HTML
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


def _parse_message(raw_message: bytes) -> Dict:
    """Parse a raw email message into a structured dict."""
    msg = email.message_from_bytes(raw_message)
    return {
        "message_id": msg.get("Message-ID", ""),
        "from": _decode_header_value(msg.get("From")),
        "to": _decode_header_value(msg.get("To")),
        "subject": _decode_header_value(msg.get("Subject")),
        "date": msg.get("Date", ""),
        "in_reply_to": msg.get("In-Reply-To", ""),
        "references": msg.get("References", ""),
        "body": _extract_body(msg),
    }


def check_inbox(folder: str = None) -> List[Dict]:
    """
    Check the inbox and return all messages in the folder.

    Args:
        folder: IMAP folder to check. Defaults to IMAP_FOLDER env var.

    Returns:
        List of parsed message dicts.
    """
    if not _is_configured():
        logger.warning("IMAP not configured (PLACEHOLDER values) - skipping check")
        return []

    folder = folder or IMAP_FOLDER
    messages = []

    try:
        client = _get_imap_client()
        client.select_folder(folder, readonly=True)
        uids = client.search(["ALL"])

        logger.info(f"Found {len(uids)} messages in {folder}")

        if uids:
            raw_messages = client.fetch(uids, ["RFC822"])
            for uid, data in raw_messages.items():
                raw = data.get(b"RFC822", data.get("RFC822", b""))
                if raw:
                    parsed = _parse_message(raw)
                    parsed["uid"] = uid
                    messages.append(parsed)

        client.logout()
    except Exception as e:
        logger.error(f"Failed to check inbox: {e}")

    return messages


def get_new_replies(since: datetime = None, folder: str = None) -> List[Dict]:
    """
    Fetch new reply emails since a given datetime.

    Args:
        since: Only fetch messages after this datetime.
               Defaults to 24 hours ago.
        folder: IMAP folder. Defaults to IMAP_FOLDER env var.

    Returns:
        List of parsed message dicts that are replies (have In-Reply-To header).
    """
    if not _is_configured():
        logger.warning("IMAP not configured - skipping reply check")
        return []

    if since is None:
        since = datetime.now(timezone.utc) - timedelta(hours=24)

    folder = folder or IMAP_FOLDER
    replies = []

    try:
        client = _get_imap_client()
        client.select_folder(folder, readonly=True)

        # Search for messages since the given date
        since_date = since.strftime("%d-%b-%Y")
        uids = client.search(["SINCE", since_date])

        logger.info(f"Found {len(uids)} messages since {since_date}")

        if uids:
            raw_messages = client.fetch(uids, ["RFC822"])
            for uid, data in raw_messages.items():
                raw = data.get(b"RFC822", data.get("RFC822", b""))
                if raw:
                    parsed = _parse_message(raw)
                    parsed["uid"] = uid
                    # Only include actual replies
                    if parsed["in_reply_to"]:
                        replies.append(parsed)

        client.logout()
        logger.info(f"Found {len(replies)} replies since {since_date}")
    except Exception as e:
        logger.error(f"Failed to get new replies: {e}")

    return replies


def parse_thread(message: Dict) -> Dict:
    """
    Parse an email message to extract thread context.

    Extracts the References header chain and identifies the original
    message ID and reply chain.

    Args:
        message: Parsed message dict (from check_inbox / get_new_replies).

    Returns:
        Dict with thread analysis:
            - original_message_id: First message in the thread
            - reply_chain: List of message IDs in order
            - is_reply: Whether this is a reply
            - thread_depth: Number of messages in the chain
    """
    references_raw = message.get("references", "")
    in_reply_to = message.get("in_reply_to", "")

    # Parse the References header into a list of message IDs
    reply_chain = []
    if references_raw:
        # Message IDs are enclosed in angle brackets
        import re
        reply_chain = re.findall(r"<[^>]+>", references_raw)

    # The first reference is the original message
    original_message_id = reply_chain[0] if reply_chain else in_reply_to or ""

    is_reply = bool(in_reply_to)

    result = {
        "original_message_id": original_message_id,
        "reply_chain": reply_chain,
        "is_reply": is_reply,
        "thread_depth": len(reply_chain) + (1 if is_reply else 0),
        "in_reply_to": in_reply_to,
        "subject": message.get("subject", ""),
        "from": message.get("from", ""),
    }

    logger.debug(f"Thread parsed: depth={result['thread_depth']}, reply={is_reply}")
    return result
