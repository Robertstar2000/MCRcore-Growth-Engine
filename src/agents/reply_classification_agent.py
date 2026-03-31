"""
MCRcore Growth Engine - Reply Classification Agent

Interprets ALL inbound replies and updates lead state accordingly.
Uses keyword pre-filtering for fast deterministic matches (bounces,
opt-outs, auto-responses) and LLM for nuanced classification of
ambiguous replies.

Classification categories:
    likely_order, interested_not_ready, neutral, not_interested,
    opt_out, bounce, auto_response, referral
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.skills.reply_intent import (
    INTENT_TAXONOMY,
    IntentCategory,
    detect_objections,
    keyword_pre_filter,
    match_bounce,
    match_buying_signals,
    match_opt_out,
    match_referral,
)
from src.utils.llm_client import classify_text, generate_text
from src.utils.teams_notifier import send_escalation_alert, send_teams_card
from db.repositories import (
    ContactRepository,
    LeadRepository,
    ReplyRepository,
    SuppressionRepository,
    AuditRepository,
    NurtureRepository,
)


# Classification categories for LLM
CLASSIFICATION_CATEGORIES = [
    "likely_order",
    "interested_not_ready",
    "neutral",
    "not_interested",
    "opt_out",
    "bounce",
    "auto_response",
    "referral",
]

# LLM system prompt for reply classification
CLASSIFICATION_SYSTEM_PROMPT = """\
You are an expert email reply classifier for an IT managed services company (MCRcore).
Classify the reply into exactly ONE of these categories:

- likely_order: Prospect wants pricing, a demo, a meeting, or is ready to buy
- interested_not_ready: Prospect shows interest but is not ready now (timing, need info)
- neutral: Non-committal acknowledgement (thanks, got it, OK)
- not_interested: Prospect declines but has not opted out
- opt_out: Prospect explicitly asks to be removed / unsubscribe
- bounce: Non-delivery report / email address invalid
- auto_response: Out-of-office or automated reply
- referral: Prospect refers or forwards to another person

Return ONLY a JSON object: {"category": "<category>", "confidence": <0.0-1.0>, "reasoning": "<brief>"}
"""


class ReplyClassificationAgent(BaseAgent):
    """
    Classifies inbound email replies, updates lead state, and triggers
    escalation or suppression as needed.
    """

    def __init__(self, session: Session):
        super().__init__(
            name="reply-classification-agent",
            description="Classifies inbound replies and updates lead state",
        )
        self.session = session
        self.lead_repo = LeadRepository(session)
        self.reply_repo = ReplyRepository(session)
        self.contact_repo = ContactRepository(session)
        self.suppression_repo = SuppressionRepository(session)
        self.audit_repo = AuditRepository(session)
        self.nurture_repo = NurtureRepository(session)

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------
    def run(self, reply_ids: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Classify one or more replies. If no reply_ids given, processes
        all unclassified replies.

        Returns summary dict of classifications.
        """
        if reply_ids is None:
            unclassified = self.reply_repo.get_unclassified(limit=100)
            reply_ids = [r.reply_id for r in unclassified]

        results = []
        for reply_id in reply_ids:
            try:
                result = self.classify_reply(reply_id)
                results.append(result)
            except Exception as e:
                self.log_action(
                    "classify_reply",
                    f"Failed to classify reply {reply_id}: {e}",
                    status="failure",
                    metadata={"reply_id": reply_id, "error": str(e)},
                )
                results.append({"reply_id": reply_id, "error": str(e)})

        summary = {
            "total_processed": len(results),
            "successful": sum(1 for r in results if "error" not in r),
            "failed": sum(1 for r in results if "error" in r),
            "classifications": results,
        }

        self.log_action(
            "run_complete",
            f"Classified {summary['successful']}/{summary['total_processed']} replies",
            metadata=summary,
        )
        return summary

    # ------------------------------------------------------------------
    # Core Classification
    # ------------------------------------------------------------------
    def classify_reply(self, reply_id: str) -> Dict[str, Any]:
        """
        Classify a single reply event by ID.

        Steps:
          1. Load reply event and lead context
          2. Run keyword pre-filter
          3. Run LLM classification if needed
          4. Detect objections
          5. Update reply event record
          6. Update lead state
          7. Handle special cases (opt-out, escalation)

        Returns classification result dict.
        """
        reply_event = self.reply_repo.get_by_id(reply_id)
        if reply_event is None:
            raise ValueError(f"Reply event not found: {reply_id}")

        text = reply_event.raw_text or ""
        lead = self.lead_repo.get_by_id(reply_event.lead_id)

        # Build thread context for LLM
        thread_context = self._build_thread_context(reply_event)

        # Step 1: Keyword pre-filter
        pre_filter = keyword_pre_filter(text)

        # Step 2: Classify
        if pre_filter["skip_llm"] and pre_filter["suggested_category"]:
            # High-confidence keyword match — no LLM needed
            category = pre_filter["suggested_category"]
            confidence = 0.95
            reasoning = f"Keyword match: {category}"
        else:
            # LLM classification (with keyword hints)
            category, confidence, reasoning = self.analyze_intent(
                text, thread_context, pre_filter
            )

        # Step 3: Detect objections
        objections = detect_objections(text)
        objection_tags = [obj["type"] for obj in objections]

        # Step 4: Determine flags
        is_opt_out = category == IntentCategory.OPT_OUT
        is_escalation = category in (
            IntentCategory.LIKELY_ORDER,
            IntentCategory.REFERRAL,
        )

        # Step 5: Update reply event record
        self.reply_repo.update(
            reply_id,
            classified_as=category,
            intent_confidence=confidence,
            objection_tags=json.dumps(objection_tags) if objection_tags else None,
            escalation_flag=is_escalation,
            opt_out_flag=is_opt_out,
        )

        # Step 6: Update lead state
        if lead:
            self.update_lead_state(lead.lead_id, category)

        # Step 7: Handle special cases
        if is_opt_out and lead:
            self._handle_opt_out(lead)

        if is_escalation:
            self._send_notification(category, reply_event, lead)

        # Audit
        self.audit_repo.log(
            actor=self.name,
            entity_type="reply_event",
            entity_id=reply_id,
            action="classify",
            after_json=json.dumps({
                "category": category,
                "confidence": confidence,
                "objections": objection_tags,
                "escalation": is_escalation,
                "opt_out": is_opt_out,
            }),
        )

        result = {
            "reply_id": reply_id,
            "lead_id": reply_event.lead_id,
            "category": category,
            "confidence": confidence,
            "reasoning": reasoning,
            "objections": objection_tags,
            "escalation_flag": is_escalation,
            "opt_out_flag": is_opt_out,
        }

        self.log_action(
            "classify_reply",
            f"Reply {reply_id[:8]}… classified as {category} "
            f"(conf={confidence:.2f})",
            metadata=result,
        )

        self.session.commit()
        return result

    def analyze_intent(
        self,
        text: str,
        thread_context: Dict[str, Any],
        pre_filter: Dict[str, Any] = None,
    ) -> Tuple[str, float, str]:
        """
        Analyze reply intent using LLM with optional keyword pre-filter hints.

        Args:
            text: Reply body text.
            thread_context: Dict with thread/conversation context.
            pre_filter: Keyword pre-filter results (optional).

        Returns:
            (category, confidence, reasoning) tuple.
        """
        hint = ""
        if pre_filter and pre_filter.get("suggested_category"):
            hint = (
                f"\nKeyword analysis suggests: {pre_filter['suggested_category']}. "
                f"Verify or override this with your analysis."
            )

        thread_info = ""
        if thread_context:
            thread_info = (
                f"\nThread context — Subject: {thread_context.get('subject', 'N/A')}, "
                f"Depth: {thread_context.get('thread_depth', 0)} messages, "
                f"Outreach stage: {thread_context.get('last_outreach_stage', 'N/A')}"
            )

        prompt = (
            f"Classify this email reply from a sales outreach thread.{hint}{thread_info}\n\n"
            f"Reply text:\n---\n{text[:2000]}\n---\n\n"
            f"Return ONLY valid JSON: "
            f'{{\"category\": \"<category>\", \"confidence\": <0.0-1.0>, \"reasoning\": \"<brief>\"}}'
        )

        try:
            raw = generate_text(
                prompt=prompt,
                system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
                max_tokens=256,
                temperature=0.0,
            )

            # Parse JSON response
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            result = json.loads(raw)

            category = result.get("category", "neutral")
            if category not in CLASSIFICATION_CATEGORIES:
                category = "neutral"

            confidence = float(result.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
            reasoning = result.get("reasoning", "LLM classification")

            return category, confidence, reasoning

        except Exception as e:
            self.logger.warning(
                f"LLM classification failed, falling back to pre-filter: {e}"
            )
            # Fall back to pre-filter suggestion or neutral
            if pre_filter and pre_filter.get("suggested_category"):
                return pre_filter["suggested_category"], 0.6, "Keyword fallback (LLM failed)"
            return "neutral", 0.3, f"Classification failed: {e}"

    def detect_buying_intent(self, text: str) -> Dict[str, Any]:
        """
        Detect buying intent in reply text.

        Returns dict with detected flag, matched patterns, and confidence.
        """
        matched, patterns = match_buying_signals(text)
        confidence = min(1.0, len(patterns) * 0.25) if matched else 0.0
        return {
            "detected": matched,
            "pattern_count": len(patterns),
            "confidence": confidence,
        }

    def detect_objections(self, text: str) -> List[Dict[str, Any]]:
        """Detect objections in reply text."""
        return detect_objections(text)

    def detect_referral(self, text: str) -> Dict[str, Any]:
        """
        Detect referral indicators in reply text.

        Returns dict with detected flag and matched patterns.
        """
        matched, patterns = match_referral(text)
        return {
            "detected": matched,
            "pattern_count": len(patterns),
        }

    def detect_opt_out(self, text: str) -> Dict[str, Any]:
        """
        Detect opt-out language in reply text.

        Returns dict with detected flag and matched patterns.
        """
        matched, patterns = match_opt_out(text)
        return {
            "detected": matched,
            "pattern_count": len(patterns),
        }

    def detect_bounce(self, raw_message: str) -> Dict[str, Any]:
        """
        Detect bounce/NDR indicators in raw message.

        Returns dict with detected flag and matched patterns.
        """
        matched, patterns = match_bounce(raw_message)
        return {
            "detected": matched,
            "pattern_count": len(patterns),
        }

    # ------------------------------------------------------------------
    # Lead State Updates
    # ------------------------------------------------------------------
    def update_lead_state(self, lead_id: str, classification: str) -> None:
        """
        Update lead status and related fields based on reply classification.

        Args:
            lead_id: The lead to update.
            classification: The classification category string.
        """
        taxonomy_entry = INTENT_TAXONOMY.get(classification, {})
        new_status = taxonomy_entry.get("status_mapping")

        if new_status is None:
            # auto_response: don't change status
            self.log_action(
                "update_lead_state",
                f"No status change for classification={classification}",
                metadata={"lead_id": lead_id, "classification": classification},
            )
            return

        update_fields = {
            "status": new_status,
            "last_processed_at": datetime.now(timezone.utc),
        }

        if classification == IntentCategory.OPT_OUT:
            update_fields["opt_out_flag"] = True
            update_fields["do_not_contact_reason"] = "opt_out_reply"

        if classification == IntentCategory.LIKELY_ORDER:
            update_fields["substatus"] = "escalation_pending"

        if classification == IntentCategory.INTERESTED_NOT_READY:
            update_fields["substatus"] = "nurture_warm"

        if classification == IntentCategory.NOT_INTERESTED:
            update_fields["substatus"] = "declined"

        if classification == IntentCategory.REFERRAL:
            update_fields["substatus"] = "referral_received"

        if classification == IntentCategory.BOUNCE:
            update_fields["substatus"] = "email_invalid"

        lead_before = self.lead_repo.get_by_id(lead_id)
        old_status = lead_before.status if lead_before else None

        self.lead_repo.update(lead_id, **update_fields)

        # Cancel pending nurtures if opted out or bounced
        if classification in (IntentCategory.OPT_OUT, IntentCategory.BOUNCE):
            cancelled = self.nurture_repo.cancel_for_lead(lead_id)
            if cancelled:
                self.log_action(
                    "cancel_nurtures",
                    f"Cancelled {cancelled} pending nurtures for lead {lead_id[:8]}…",
                    metadata={"lead_id": lead_id, "cancelled_count": cancelled},
                )

        self.audit_repo.log(
            actor=self.name,
            entity_type="lead",
            entity_id=lead_id,
            action="status_change",
            before_json=json.dumps({"status": old_status}),
            after_json=json.dumps(update_fields),
        )

        self.log_action(
            "update_lead_state",
            f"Lead {lead_id[:8]}… status: {old_status} -> {new_status}",
            metadata={"lead_id": lead_id, "old_status": old_status, "new_status": new_status},
        )

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------
    def _build_thread_context(self, reply_event) -> Dict[str, Any]:
        """Build thread context dict from reply event and related outreach."""
        context = {
            "thread_id": reply_event.thread_id or "",
            "subject": "",
            "thread_depth": 0,
            "last_outreach_stage": "",
        }

        if reply_event.lead_id:
            # Get prior replies in this thread
            prior_replies = self.reply_repo.get_by_lead(reply_event.lead_id)
            context["thread_depth"] = len(prior_replies)

            # Get last outreach for context
            from db.repositories import OutreachRepository
            outreach_repo = OutreachRepository(self.session)
            outreach_events = outreach_repo.get_by_lead(reply_event.lead_id)
            if outreach_events:
                latest = outreach_events[0]  # Already sorted desc
                context["last_outreach_stage"] = latest.stage or ""
                context["subject"] = latest.subject or ""

        return context

    def _handle_opt_out(self, lead) -> None:
        """Create suppression record and mark contact as DNC."""
        contact = self.contact_repo.get_by_id(lead.contact_id) if lead.contact_id else None
        if contact and contact.email:
            self.suppression_repo.suppress(
                email=contact.email,
                reason="opt_out_reply",
                source=self.name,
            )
            self.contact_repo.update(contact.contact_id, do_not_contact=True)

            self.log_action(
                "create_suppression",
                f"Suppressed {contact.email} — opt-out reply",
                metadata={
                    "email": contact.email,
                    "lead_id": lead.lead_id,
                },
            )

    def _send_notification(self, category: str, reply_event, lead) -> None:
        """Send Teams notification for high-priority classifications."""
        company_name = "Unknown"
        contact_name = "Unknown"
        contact_email = "Unknown"

        if lead:
            if lead.company:
                company_name = lead.company.company_name or "Unknown"
            if lead.contact:
                contact_name = lead.contact.full_name or "Unknown"
                contact_email = lead.contact.email or "Unknown"

        if category == IntentCategory.LIKELY_ORDER:
            send_escalation_alert({
                "company": company_name,
                "contact": f"{contact_name} ({contact_email})",
                "value": "Pending assessment",
                "reason": "Positive reply — buying intent detected",
                "recommended_action": "Review reply and escalate to sales",
            })
        elif category == IntentCategory.REFERRAL:
            send_teams_card(
                title=f"🤝 Referral Detected: {company_name}",
                facts=[
                    {"title": "Company", "value": company_name},
                    {"title": "Contact", "value": f"{contact_name} ({contact_email})"},
                    {"title": "Classification", "value": "Referral"},
                    {"title": "Reply Preview", "value": (reply_event.raw_text or "")[:200]},
                    {"title": "Action", "value": "Review referral and update contact records"},
                ],
            )
