"""
MCRcore Growth Engine - Mailbox Processing Service

Orchestrates the full reply processing pipeline:
  fetch inbox -> match to lead -> store reply event -> classify -> escalate

Connects inbound replies to the originating lead via thread_id (Message-ID /
In-Reply-To / References headers) or sender email matching.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.agents.reply_classification_agent import ReplyClassificationAgent
from src.agents.escalation_agent import EscalationAgent
from src.utils.email_receiver import get_new_replies, parse_thread
from src.utils.logger import setup_logger
from db.models import Lead, ReplyEvent
from db.repositories import (
    ContactRepository,
    LeadRepository,
    OpportunityRepository,
    OutreachRepository,
    ReplyRepository,
    AuditRepository,
)

logger = setup_logger("mcr_growth_engine.mailbox_processor")


class MailboxProcessorService:
    """
    Processes the MCRcore reply inbox end-to-end:
    fetch -> match -> store -> classify -> escalate (if needed).
    """

    def __init__(self, session: Session):
        """
        Args:
            session: SQLAlchemy session.
        """
        self.session = session
        self.lead_repo = LeadRepository(session)
        self.contact_repo = ContactRepository(session)
        self.outreach_repo = OutreachRepository(session)
        self.reply_repo = ReplyRepository(session)
        self.audit_repo = AuditRepository(session)

        self.classification_agent = ReplyClassificationAgent(session)
        self.escalation_agent = EscalationAgent(session)

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------
    def process_inbox(
        self,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Fetch new replies and process them through the full pipeline.

        Args:
            since: Only fetch messages since this datetime.
                   Defaults to 24 hours ago (handled by email_receiver).

        Returns:
            Summary dict with counts and results.
        """
        logger.info("Starting mailbox processing run")

        # Step 1: Fetch new replies from IMAP
        raw_messages = get_new_replies(since=since)
        logger.info(f"Fetched {len(raw_messages)} new replies from inbox")

        if not raw_messages:
            logger.info("No new replies to process")
            return {
                "fetched": 0,
                "matched": 0,
                "stored": 0,
                "classified": 0,
                "escalated": 0,
                "unmatched": 0,
                "errors": [],
            }

        matched_count = 0
        stored_count = 0
        classified_count = 0
        escalated_count = 0
        unmatched_count = 0
        errors = []
        stored_reply_ids = []

        for message in raw_messages:
            try:
                # Step 2: Match reply to a lead
                lead_id = self.match_reply_to_lead(message)

                if lead_id is None:
                    unmatched_count += 1
                    logger.debug(
                        f"No lead match for reply from {message.get('from', 'unknown')}"
                    )
                    continue

                matched_count += 1

                # Step 3: Create reply event record
                reply_event = self.create_reply_event(message, lead_id)
                stored_count += 1
                stored_reply_ids.append(reply_event.reply_id)

            except Exception as e:
                errors.append({
                    "phase": "match_and_store",
                    "message_from": message.get("from", "unknown"),
                    "error": str(e),
                })
                logger.error(f"Error processing reply from {message.get('from', 'unknown')}: {e}")

        # Step 4: Run classification on all stored replies
        for reply_id in stored_reply_ids:
            try:
                classification = self.run_classification(reply_id)
                classified_count += 1

                # Step 5: Check for escalation
                reply_event = self.reply_repo.get_by_id(reply_id)
                if reply_event and reply_event.escalation_flag:
                    escalation_result = self.check_for_escalation(reply_event.lead_id)
                    if escalation_result.get("escalated"):
                        escalated_count += 1

            except Exception as e:
                errors.append({
                    "phase": "classify_or_escalate",
                    "reply_id": reply_id,
                    "error": str(e),
                })
                logger.error(f"Error classifying/escalating reply {reply_id}: {e}")

        summary = {
            "fetched": len(raw_messages),
            "matched": matched_count,
            "stored": stored_count,
            "classified": classified_count,
            "escalated": escalated_count,
            "unmatched": unmatched_count,
            "errors": errors,
        }

        logger.info(
            f"Mailbox processing complete: "
            f"fetched={summary['fetched']}, matched={summary['matched']}, "
            f"classified={summary['classified']}, escalated={summary['escalated']}, "
            f"unmatched={summary['unmatched']}, errors={len(errors)}"
        )

        return summary

    # ------------------------------------------------------------------
    # Reply-to-Lead Matching
    # ------------------------------------------------------------------
    def match_reply_to_lead(self, message: Dict[str, Any]) -> Optional[str]:
        """
        Match an inbound reply to its originating lead.

        Matching strategies (in priority order):
          1. Thread ID match: In-Reply-To or References -> OutreachEvent.body_hash
             (we store outbound Message-ID as body_hash in some configurations)
          2. Email sender match: From address -> Contact.email -> Lead

        Args:
            message: Parsed email message dict from email_receiver.

        Returns:
            lead_id if matched, None otherwise.
        """
        # Strategy 1: Thread-based matching via In-Reply-To / References
        thread_info = parse_thread(message)
        original_message_id = thread_info.get("original_message_id", "")
        in_reply_to = thread_info.get("in_reply_to", "")
        reply_chain = thread_info.get("reply_chain", [])

        # Check all message IDs in the thread for a match
        message_ids_to_check = []
        if in_reply_to:
            message_ids_to_check.append(in_reply_to)
        if original_message_id and original_message_id != in_reply_to:
            message_ids_to_check.append(original_message_id)
        message_ids_to_check.extend(reply_chain)

        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for mid in message_ids_to_check:
            if mid and mid not in seen:
                seen.add(mid)
                unique_ids.append(mid)

        # Try to match thread IDs against existing reply events
        for mid in unique_ids:
            existing_reply = (
                self.session.query(ReplyEvent)
                .filter(ReplyEvent.thread_id == mid)
                .first()
            )
            if existing_reply:
                return existing_reply.lead_id

        # Strategy 2: Sender email -> Contact -> Lead
        sender_email = self._extract_email(message.get("from", ""))
        if sender_email:
            contact = self.contact_repo.find_by_email(sender_email)
            if contact:
                # Find the most recent lead for this contact
                lead = (
                    self.session.query(Lead)
                    .filter(Lead.contact_id == contact.contact_id)
                    .order_by(Lead.created_at.desc())
                    .first()
                )
                if lead:
                    return lead.lead_id

        return None

    # ------------------------------------------------------------------
    # Reply Event Creation
    # ------------------------------------------------------------------
    def create_reply_event(
        self,
        message: Dict[str, Any],
        lead_id: str,
    ):
        """
        Create a ReplyEvent record from a parsed email message.

        Args:
            message: Parsed email message dict.
            lead_id: The matched lead ID.

        Returns:
            The created ReplyEvent ORM object.
        """
        thread_info = parse_thread(message)

        # Determine the best thread_id to store
        thread_id = (
            message.get("in_reply_to")
            or thread_info.get("original_message_id")
            or message.get("message_id")
            or ""
        )

        reply_event = self.reply_repo.create(
            lead_id=lead_id,
            thread_id=thread_id,
            received_at=datetime.now(timezone.utc),
            raw_text=message.get("body", ""),
            classified_as=None,  # Will be set by classification
            intent_confidence=0.0,
        )

        self.audit_repo.log(
            actor="mailbox_processor",
            entity_type="reply_event",
            entity_id=reply_event.reply_id,
            action="create",
            after_json=f'{{"lead_id": "{lead_id}", "thread_id": "{thread_id}"}}',
        )

        logger.info(
            f"Created reply event {reply_event.reply_id[:8]}… "
            f"for lead {lead_id[:8]}…"
        )

        self.session.flush()
        return reply_event

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    def run_classification(self, reply_id: str) -> Dict[str, Any]:
        """
        Run the reply classification agent on a single reply.

        Args:
            reply_id: The reply event to classify.

        Returns:
            Classification result dict.
        """
        result = self.classification_agent.classify_reply(reply_id)
        logger.info(
            f"Reply {reply_id[:8]}… classified as "
            f"{result.get('category', 'unknown')} "
            f"(confidence={result.get('confidence', 0):.2f})"
        )
        return result

    # ------------------------------------------------------------------
    # Escalation Check
    # ------------------------------------------------------------------
    def check_for_escalation(self, lead_id: str) -> Dict[str, Any]:
        """
        Check if a lead should be escalated and trigger escalation if so.

        Escalation criteria:
          - Reply classified as likely_order or referral
          - Lead not already escalated
          - No existing open opportunity

        Args:
            lead_id: The lead to check.

        Returns:
            Dict with escalation status.
        """
        lead = self.lead_repo.get_by_id(lead_id)
        if lead is None:
            return {"escalated": False, "reason": "lead_not_found"}

        # Already escalated?
        if lead.status == "escalated":
            return {"escalated": False, "reason": "already_escalated"}

        # Has an open opportunity?
        opp_repo = OpportunityRepository(self.session)
        existing_opps = opp_repo.get_by_lead(lead_id)
        open_opps = [o for o in existing_opps if o.status == "open"]
        if open_opps:
            return {"escalated": False, "reason": "open_opportunity_exists"}

        # Check for escalation-flagged replies
        replies = self.reply_repo.get_by_lead(lead_id)
        escalation_replies = [r for r in replies if r.escalation_flag]

        if not escalation_replies:
            return {"escalated": False, "reason": "no_escalation_trigger"}

        # Trigger escalation
        try:
            result = self.escalation_agent.escalate_opportunity(lead_id)
            return {
                "escalated": True,
                "opportunity_id": result.get("opportunity_id"),
                "lead_id": lead_id,
            }
        except Exception as e:
            logger.error(f"Escalation failed for lead {lead_id}: {e}")
            return {"escalated": False, "reason": f"escalation_failed: {e}"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_email(from_header: str) -> Optional[str]:
        """
        Extract email address from a From header value.

        Handles formats like:
            "John Smith <john@example.com>"
            "john@example.com"
        """
        if not from_header:
            return None
        match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", from_header)
        return match.group(0).lower() if match else None
