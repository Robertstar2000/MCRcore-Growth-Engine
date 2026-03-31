"""
MCRcore Growth Engine - Outreach Personalization Agent

Generates personalized, context-aware outreach emails for leads.

Responsibilities:
  - Load full lead context (company, contact, enrichment, signals, score, prior outreach)
  - Select the most relevant 1-3 differentiators per lead
  - Pick the right template (audit-first vs. package-specific, by title and stage)
  - Personalize the template using LLM with lead-specific context
  - Check body hash uniqueness against prior sends
  - Create OutreachEvent records
  - Ensure compliance footer is always present

Stages: first_touch, day_7, day_30, day_90
"""

import hashlib
import json
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.agents.base_agent import BaseAgent
from src.templates.message_blocks import (
    COMPLIANCE_FOOTER,
    DIFFERENTIATOR_BLOCKS,
    INDUSTRY_BLOCKS,
    PACKAGE_BLOCKS,
    TITLE_BLOCKS,
)
from src.skills.audit_first_outreach import (
    AUDIT_FIRST_TEMPLATES,
    CTA_VARIANTS,
    FOLLOWUP_TEMPLATES,
    get_audit_template,
    get_cta,
    get_followup_template,
    list_followup_angles,
)
from src.skills.package_specific_email import (
    PACKAGE_EMAIL_TEMPLATES,
    build_package_email,
    get_package_opener,
    get_package_template,
)
from config.differentiators import DIFFERENTIATOR_BLOCKS as DIFF_CONFIG
from config.service_catalog import SERVICES


# ===================================================================
# Constants
# ===================================================================

VALID_STAGES = ("first_touch", "day_7", "day_30", "day_90")

MCRCORE_COMPLIANCE_FOOTER = (
    "\n---\n"
    "MCRcore | Managed IT & Cybersecurity\n"
    "136 W. Official Road, Addison, IL 60101\n"
    "If you'd prefer not to receive these emails, reply STOP or "
    "click here to unsubscribe: {{ unsubscribe_url }}\n"
)

LLM_SYSTEM_PROMPT = (
    "You are a senior sales copywriter for MCRcore, a managed IT and cybersecurity "
    "company. You write outreach emails that are specific, informed, and concise. "
    "You never use generic MSP boilerplate. You always reference concrete business "
    "context. You tie value to uptime, growth, security, or stability. You match "
    "tone and content to the buyer's title and industry. You keep emails under "
    "250 words (body only, excluding signature and footer). You write in a "
    "professional but conversational tone — no buzzwords, no filler."
)


# ===================================================================
# Title / Industry Matching Helpers
# ===================================================================

def _classify_title(title: str) -> str:
    """Map a contact title string to a title block key."""
    if not title:
        return "ceo_owner"
    title_lower = title.lower()
    for key, block in TITLE_BLOCKS.items():
        for match in block["match_titles"]:
            if match in title_lower:
                return key
    return "ceo_owner"  # default


def _classify_industry(industry: str) -> str:
    """Map an industry string to an industry block key."""
    if not industry:
        return "smb"
    industry_lower = industry.lower()
    for key, block in INDUSTRY_BLOCKS.items():
        for match in block["match_keywords"]:
            if match in industry_lower:
                return key
    return "smb"  # default


def _compute_body_hash(body: str) -> str:
    """SHA-256 hash of the email body for uniqueness checking."""
    normalized = " ".join(body.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ===================================================================
# Outreach Personalization Agent
# ===================================================================

class OutreachPersonalizationAgent(BaseAgent):
    """
    Generates personalized outreach emails for leads at every nurture stage.

    Uses lead context (company, contact, enrichment, signals, score) to
    select templates, differentiators, and CTA variants, then personalizes
    via LLM to produce unique, context-aware emails.
    """

    def __init__(self):
        super().__init__(
            name="outreach-personalization",
            description=(
                "Generates personalized, context-aware outreach emails for "
                "leads across all nurture stages."
            ),
        )
        self._llm_available = True
        try:
            from src.utils.llm_client import generate_text
            self._generate_text = generate_text
        except Exception:
            self._llm_available = False
            self._generate_text = None
            self.logger.warning("LLM client unavailable; templates will be returned with placeholders")

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def run(self, lead_id: str, stage: str = "first_touch", session=None) -> Dict[str, Any]:
        """
        Primary entry point. Generate outreach for a lead at a given stage.

        Args:
            lead_id: UUID of the lead.
            stage: One of 'first_touch', 'day_7', 'day_30', 'day_90'.
            session: SQLAlchemy session (optional; if None, runs in template-only mode).

        Returns:
            Dict with keys: lead_id, stage, subject, body, body_hash,
            differentiators_used, outreach_id, status.
        """
        return self.generate_outreach(lead_id, stage=stage, session=session)

    def generate_outreach(
        self,
        lead_id: str,
        stage: str = "first_touch",
        session=None,
    ) -> Dict[str, Any]:
        """
        Full outreach generation pipeline.

        1. Load lead context from DB (or use minimal context if no session)
        2. Select template based on stage, title, industry, package
        3. Select differentiators
        4. Personalize via LLM
        5. Check uniqueness
        6. Create OutreachEvent record
        """
        if stage not in VALID_STAGES:
            self.log_action("generate_outreach", f"Invalid stage: {stage}", status="failure")
            return {"lead_id": lead_id, "stage": stage, "status": "error", "error": f"Invalid stage: {stage}"}

        # Load lead data
        lead_data = self._load_lead_data(lead_id, session)
        if lead_data.get("error"):
            self.log_action("generate_outreach", lead_data["error"], status="failure")
            return {"lead_id": lead_id, "stage": stage, "status": "error", "error": lead_data["error"]}

        # Route to stage-specific generation
        if stage == "first_touch":
            result = self.generate_first_touch(lead_data)
        else:
            result = self.generate_followup(lead_data, stage)

        # Check uniqueness
        if session and result.get("body"):
            uniqueness = self.check_uniqueness(lead_id, result["body"], session)
            if not uniqueness["is_unique"]:
                self.log_action(
                    "uniqueness_check",
                    f"Duplicate body hash for lead {lead_id}, regenerating",
                    status="warning",
                )
                # Vary the angle and retry once
                result = self.vary_angle(lead_data, stage)

        # Create OutreachEvent record
        outreach_id = None
        if session and result.get("body"):
            outreach_id = self._create_outreach_event(lead_id, result, stage, session)

        result["lead_id"] = lead_id
        result["stage"] = stage
        result["outreach_id"] = outreach_id
        result["status"] = "generated"

        self.log_action(
            "generate_outreach",
            f"Generated {stage} outreach for lead {lead_id[:8]}",
            metadata={"stage": stage, "outreach_id": outreach_id},
        )

        return result

    def generate_first_touch(self, lead_data: Dict) -> Dict[str, Any]:
        """
        Generate a first-touch email. Uses audit-first for high-fit leads
        and package-specific for leads with clear package match.
        """
        title_key = lead_data.get("title_key", "ceo_owner")
        industry_key = lead_data.get("industry_key", "smb")
        recommended_package = lead_data.get("recommended_offer", "")
        priority_tier = lead_data.get("priority_tier", "C")

        # Select differentiators
        differentiators = self.select_differentiators(lead_data, max_count=2)
        diff_text = self._format_differentiators(differentiators)

        # Decision: audit-first vs. package-specific
        # Use audit-first for: Tier A/B, no clear package, or CEO/CFO titles
        use_audit_first = (
            priority_tier in ("A", "B")
            or not recommended_package
            or title_key in ("ceo_owner", "cfo_controller")
        )

        if use_audit_first:
            template = get_audit_template(title_key)
            subject = self._select_subject(template["subject_lines"])
            cta = self._select_cta(title_key)
            opener = self._select_opener(title_key, industry_key)

            body = template["body"]
        else:
            # Package-specific email
            pkg_key = self._normalize_package_key(recommended_package)
            email_parts = build_package_email(pkg_key, title_key, lead_data)
            subject = email_parts.get("subject", "")
            body = email_parts.get("body", "")
            opener = get_package_opener(pkg_key, title_key)
            cta = PACKAGE_BLOCKS.get(pkg_key, {}).get("cta_variants", [""])[0]

        # Build lead context for personalization
        lead_context = self._build_lead_context(lead_data)
        lead_context["differentiator_block"] = diff_text
        lead_context["cta"] = cta
        lead_context["opener"] = opener
        lead_context["compliance_footer"] = MCRCORE_COMPLIANCE_FOOTER

        # Personalize via LLM
        personalized_body = self.personalize_message(body, lead_context)
        personalized_subject = self._fill_placeholders(subject, lead_context)

        # Ensure compliance footer
        if "136 W. Official Road" not in personalized_body:
            personalized_body += MCRCORE_COMPLIANCE_FOOTER

        body_hash = _compute_body_hash(personalized_body)

        return {
            "subject": personalized_subject,
            "body": personalized_body,
            "body_hash": body_hash,
            "differentiators_used": [d["id"] for d in differentiators],
            "template_type": "audit_first" if use_audit_first else "package_specific",
            "package_angle": recommended_package or "technical_audit",
        }

    def generate_followup(self, lead_data: Dict, stage: str) -> Dict[str, Any]:
        """
        Generate a follow-up email for day_7, day_30, or day_90.

        Each stage uses materially different angles, subjects, and framing
        to avoid repetitive messaging.
        """
        title_key = lead_data.get("title_key", "ceo_owner")
        industry_key = lead_data.get("industry_key", "smb")

        # Select differentiators (different set for follow-ups)
        differentiators = self.select_differentiators(lead_data, max_count=2)
        diff_text = self._format_differentiators(differentiators)

        # Get follow-up template
        followup = get_followup_template(stage)
        subject = self._select_subject(followup["subject_lines"])

        # Select an angle
        angles = list(followup["angles"].keys())
        angle_key = self._select_angle(lead_data, stage, angles)
        body_template = followup["angles"][angle_key]

        # Build context
        lead_context = self._build_lead_context(lead_data)
        lead_context["differentiator_block"] = diff_text
        lead_context["cta"] = self._select_cta(title_key)
        lead_context["compliance_footer"] = MCRCORE_COMPLIANCE_FOOTER
        lead_context["original_subject"] = lead_data.get("last_subject", "my previous note")
        lead_context["title_category"] = TITLE_BLOCKS.get(title_key, {}).get("label", "business leader")

        # Stage-specific context
        if stage == "day_30":
            pkg_key = self._normalize_package_key(lead_data.get("recommended_offer", ""))
            pkg_block = PACKAGE_BLOCKS.get(pkg_key, {})
            lead_context["package_value_prop"] = pkg_block.get("value_prop", "")
        elif stage == "day_90":
            lead_context["trigger_context"] = self._build_trigger_context(lead_data)
            lead_context["new_offer_context"] = self._build_new_offer_context(lead_data)

        # Add resource placeholder for day_7
        lead_context["resource_link"] = "{{ resource_link }}"

        # Personalize
        personalized_body = self.personalize_message(body_template, lead_context)
        personalized_subject = self._fill_placeholders(subject, lead_context)

        # Ensure compliance footer
        if "136 W. Official Road" not in personalized_body:
            personalized_body += MCRCORE_COMPLIANCE_FOOTER

        body_hash = _compute_body_hash(personalized_body)

        return {
            "subject": personalized_subject,
            "body": personalized_body,
            "body_hash": body_hash,
            "differentiators_used": [d["id"] for d in differentiators],
            "template_type": f"followup_{stage}",
            "angle_used": angle_key,
            "package_angle": lead_data.get("recommended_offer", "technical_audit"),
        }

    def personalize_message(self, template: str, lead_context: Dict) -> str:
        """
        Personalize a template using LLM and lead context.

        First fills known placeholders, then uses LLM to refine
        the message with lead-specific business context.
        """
        # Step 1: Fill known Jinja2-style placeholders
        filled = self._fill_placeholders(template, lead_context)

        # Step 2: LLM personalization (if available)
        if self._llm_available and self._generate_text:
            try:
                prompt = self._build_personalization_prompt(filled, lead_context)
                personalized = self._generate_text(
                    prompt=prompt,
                    system_prompt=LLM_SYSTEM_PROMPT,
                    max_tokens=800,
                    temperature=0.7,
                )
                # Ensure compliance footer survived LLM generation
                if "136 W. Official Road" not in personalized:
                    personalized += MCRCORE_COMPLIANCE_FOOTER
                return personalized
            except Exception as e:
                self.logger.warning(f"LLM personalization failed, using template fill: {e}")
                return filled
        else:
            return filled

    def select_differentiators(
        self,
        lead_data: Dict,
        max_count: int = 3,
    ) -> List[Dict]:
        """
        Select the most relevant differentiators for a lead.

        Scoring considers:
        - Industry match
        - Title match
        - Signal profile (ERP signals, scaling signals)
        - Prior outreach (avoid repeating same differentiators)
        """
        title_key = lead_data.get("title_key", "ceo_owner")
        industry_key = lead_data.get("industry_key", "smb")
        prior_diffs = set(lead_data.get("prior_differentiators", []))

        scored: List[Tuple[float, str, Dict]] = []

        for diff_id, diff_block in DIFFERENTIATOR_BLOCKS.items():
            score = 0.0

            # Industry match
            if industry_key in diff_block.get("best_for_industries", []):
                score += 3.0

            # Title match
            if title_key in diff_block.get("best_for_titles", []):
                score += 2.0

            # ERP signal boost for ERP expertise differentiator
            if diff_id == "deep_erp_expertise":
                erp_signals = lead_data.get("erp_signals", "")
                if erp_signals:
                    score += 2.0
                epicor_signal = lead_data.get("epicor_signal", 0.0)
                if epicor_signal and epicor_signal > 0.3:
                    score += 1.5

            # Scaling signal boost
            if diff_id in ("fractional_cio_access", "not_generic_msp"):
                scaling = lead_data.get("scaling_signal", 0.0)
                if scaling and scaling > 0.3:
                    score += 1.5

            # 24/7 monitoring boost for companies with downtime pain
            if diff_id == "24_7_monitoring":
                infra = lead_data.get("infrastructure_signals", "")
                if infra:
                    score += 1.0

            # Audit-first always gets a base score
            if diff_id == "audit_first_engagement":
                score += 1.0

            # Penalize recently used differentiators
            if diff_id in prior_diffs:
                score -= 5.0

            # Small random factor for variety
            score += random.uniform(0, 0.5)

            scored.append((score, diff_id, {
                "id": diff_id,
                "short_insert": diff_block.get("short_insert", ""),
                "one_liner": diff_block.get("one_liner", ""),
                "proof_line": diff_block.get("proof_line", ""),
            }))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        return [item[2] for item in scored[:max_count]]

    def check_uniqueness(
        self,
        lead_id: str,
        draft: str,
        session=None,
    ) -> Dict[str, Any]:
        """
        Check if the draft body hash is unique against prior sends for this lead.

        Returns:
            Dict with 'is_unique' bool and 'matching_outreach_id' if duplicate.
        """
        body_hash = _compute_body_hash(draft)

        if not session:
            return {"is_unique": True, "body_hash": body_hash}

        try:
            from db.repositories import OutreachRepository
            repo = OutreachRepository(session)
            prior = repo.get_by_lead(lead_id)
            for event in prior:
                if event.body_hash == body_hash:
                    return {
                        "is_unique": False,
                        "body_hash": body_hash,
                        "matching_outreach_id": event.outreach_id,
                    }
        except Exception as e:
            self.logger.warning(f"Uniqueness check failed: {e}")

        return {"is_unique": True, "body_hash": body_hash}

    def vary_angle(self, lead_data: Dict, stage: str) -> Dict[str, Any]:
        """
        Generate a varied version of an outreach email when the first
        attempt was a duplicate. Uses a different angle/CTA/differentiator
        combination.
        """
        # Shuffle differentiator preference by adding more randomness
        original_prior = lead_data.get("prior_differentiators", [])
        lead_data["prior_differentiators"] = original_prior + lead_data.get("last_differentiators_used", [])

        if stage == "first_touch":
            return self.generate_first_touch(lead_data)
        else:
            return self.generate_followup(lead_data, stage)

    # -----------------------------------------------------------------
    # Private Helpers — Data Loading
    # -----------------------------------------------------------------

    def _load_lead_data(self, lead_id: str, session=None) -> Dict[str, Any]:
        """
        Load complete lead context from DB, or return minimal stub.
        """
        if not session:
            return {
                "lead_id": lead_id,
                "first_name": "there",
                "company_name": "your company",
                "industry": "",
                "industry_key": "smb",
                "title": "",
                "title_key": "ceo_owner",
                "recommended_offer": "",
                "priority_tier": "C",
            }

        try:
            from db.repositories import (
                LeadRepository,
                CompanyRepository,
                ContactRepository,
                EnrichmentRepository,
                SignalRepository,
                ScoreRepository,
                OutreachRepository,
            )

            lead_repo = LeadRepository(session)
            lead = lead_repo.get_by_id(lead_id)
            if not lead:
                return {"error": f"Lead {lead_id} not found"}

            data: Dict[str, Any] = {
                "lead_id": lead_id,
                "recommended_offer": lead.recommended_offer or "",
                "recommended_entry_cta": lead.recommended_entry_cta or "",
                "status": lead.status,
            }

            # Company
            if lead.company_id:
                company_repo = CompanyRepository(session)
                company = company_repo.get_by_id(lead.company_id)
                if company:
                    data["company_name"] = company.company_name or "your company"
                    data["domain"] = company.domain or ""
                    data["industry"] = company.industry or ""
                    data["industry_key"] = _classify_industry(company.industry)
                    data["employee_band"] = company.employee_band or ""
                    data["geography"] = company.geography or ""
                    data["company_summary"] = company.summary or ""
                else:
                    data["company_name"] = "your company"
                    data["industry_key"] = "smb"

            # Contact
            if lead.contact_id:
                contact_repo = ContactRepository(session)
                contact = contact_repo.get_by_id(lead.contact_id)
                if contact:
                    full_name = contact.full_name or ""
                    data["first_name"] = full_name.split()[0] if full_name else "there"
                    data["full_name"] = full_name
                    data["title"] = contact.title or ""
                    data["title_key"] = _classify_title(contact.title)
                    data["email"] = contact.email or ""
                else:
                    data["first_name"] = "there"
                    data["title_key"] = "ceo_owner"

            # Enrichment
            enrichment_repo = EnrichmentRepository(session)
            enrichment = enrichment_repo.get_by_lead(lead_id)
            if enrichment:
                data["operational_pain_summary"] = enrichment.operational_pain_summary or ""
                data["it_pain_points"] = enrichment.it_pain_points or ""
                data["erp_signals"] = enrichment.erp_signals or ""
                data["compliance_signals"] = enrichment.compliance_signals or ""
                data["remote_work_signals"] = enrichment.remote_work_signals or ""
                data["infrastructure_signals"] = enrichment.infrastructure_signals or ""
                data["company_summary"] = enrichment.company_summary or data.get("company_summary", "")
                data["research_confidence"] = enrichment.research_confidence or 0.0

            # Signals
            signal_repo = SignalRepository(session)
            signals = signal_repo.get_by_lead(lead_id)
            if signals:
                data["epicor_signal"] = signals.epicor_signal or 0.0
                data["por_signal"] = signals.por_signal or 0.0
                data["mcleod_signal"] = signals.mcleod_signal or 0.0
                data["dat_keypoint_signal"] = signals.dat_keypoint_signal or 0.0
                data["manufacturing_signal"] = signals.manufacturing_signal or 0.0
                data["logistics_signal"] = signals.logistics_signal or 0.0
                data["insurance_signal"] = signals.insurance_signal or 0.0
                data["scaling_signal"] = signals.scaling_signal or 0.0

            # Score
            score_repo = ScoreRepository(session)
            score = score_repo.get_latest_for_lead(lead_id)
            if score:
                data["fit_score"] = score.fit_score or 0.0
                data["need_score"] = score.need_score or 0.0
                data["priority_tier"] = score.priority_tier or "C"
                data["sales_probability"] = score.sales_probability or 0.0
                data["recommended_action"] = score.recommended_action or ""

            # Prior outreach
            outreach_repo = OutreachRepository(session)
            prior_outreach = outreach_repo.get_by_lead(lead_id)
            data["prior_outreach_count"] = len(prior_outreach)
            data["prior_body_hashes"] = [e.body_hash for e in prior_outreach if e.body_hash]
            data["prior_stages"] = [e.stage for e in prior_outreach if e.stage]
            data["prior_differentiators"] = []  # TODO: parse from package_angle field
            if prior_outreach:
                data["last_subject"] = prior_outreach[0].subject or ""
                data["last_stage"] = prior_outreach[0].stage or ""

            # Set defaults for missing fields
            data.setdefault("first_name", "there")
            data.setdefault("company_name", "your company")
            data.setdefault("industry_key", "smb")
            data.setdefault("title_key", "ceo_owner")
            data.setdefault("priority_tier", "C")
            data.setdefault("industry", "")

            return data

        except Exception as e:
            self.logger.error(f"Failed to load lead data: {e}")
            return {"error": f"Failed to load lead data: {e}"}

    # -----------------------------------------------------------------
    # Private Helpers — Template Selection & Filling
    # -----------------------------------------------------------------

    def _select_subject(self, subject_lines: List[str]) -> str:
        """Pick a subject line, with some randomness."""
        if not subject_lines:
            return ""
        return random.choice(subject_lines)

    def _select_cta(self, title_key: str) -> str:
        """Select a CTA variant appropriate for the title."""
        if title_key in ("ceo_owner", "cfo_controller"):
            variants = ["free_diagnostic", "30_min_walkthrough"]
        elif title_key == "it_manager":
            variants = ["no_cost_systems_review", "free_diagnostic"]
        else:
            variants = ["free_diagnostic", "no_cost_systems_review", "30_min_walkthrough"]
        return get_cta(random.choice(variants))

    def _select_opener(self, title_key: str, industry_key: str) -> str:
        """Select an opener from the title block."""
        block = TITLE_BLOCKS.get(title_key, TITLE_BLOCKS["ceo_owner"])
        openers = block.get("openers", [])
        return random.choice(openers) if openers else ""

    def _select_angle(self, lead_data: Dict, stage: str, angles: List[str]) -> str:
        """Select the best follow-up angle based on lead context and prior outreach."""
        prior_stages = lead_data.get("prior_stages", [])

        # Prefer angles that map to lead context
        if stage == "day_7":
            # Cost of inaction for high-priority leads
            if lead_data.get("priority_tier") in ("A", "B") and "cost_of_inaction" in angles:
                return "cost_of_inaction"
            # Social proof for others
            if "social_proof" in angles:
                return "social_proof"

        if stage == "day_30":
            # Package intro if we have a recommended offer
            if lead_data.get("recommended_offer") and "package_intro" in angles:
                return "package_intro"
            if "industry_trend" in angles:
                return "industry_trend"

        if stage == "day_90":
            # Trigger event if we have enrichment
            if lead_data.get("operational_pain_summary") and "trigger_event" in angles:
                return "trigger_event"
            if "competitor_gap" in angles:
                return "competitor_gap"

        return random.choice(angles)

    def _normalize_package_key(self, offer: str) -> str:
        """Normalize a recommended offer string to a service catalog key."""
        if not offer:
            return "technical_audit"
        normalized = offer.lower().replace(" ", "_").replace("-", "_")
        if normalized in SERVICES:
            return normalized
        # Fuzzy match
        for key in SERVICES:
            if key in normalized or normalized in key:
                return key
        return "technical_audit"

    def _format_differentiators(self, differentiators: List[Dict]) -> str:
        """Format selected differentiators as an email-ready text block."""
        if not differentiators:
            return ""
        parts = []
        for diff in differentiators:
            insert = diff.get("short_insert", "")
            if insert:
                parts.append(insert)
        return "\n\n".join(parts)

    def _build_lead_context(self, lead_data: Dict) -> Dict[str, str]:
        """Build a flat dict of placeholder values from lead data."""
        industry_key = lead_data.get("industry_key", "smb")
        industry_label = INDUSTRY_BLOCKS.get(industry_key, {}).get("label", "your industry")

        return {
            "first_name": lead_data.get("first_name", "there"),
            "full_name": lead_data.get("full_name", ""),
            "company_name": lead_data.get("company_name", "your company"),
            "industry": industry_label,
            "title": lead_data.get("title", ""),
            "employee_band": lead_data.get("employee_band", ""),
            "geography": lead_data.get("geography", ""),
            "domain": lead_data.get("domain", ""),
            "company_summary": lead_data.get("company_summary", ""),
            "operational_pain_summary": lead_data.get("operational_pain_summary", ""),
            "it_pain_points": lead_data.get("it_pain_points", ""),
            "erp_signals": lead_data.get("erp_signals", ""),
            "compliance_signals": lead_data.get("compliance_signals", ""),
            "preferred_day": "next Tuesday or Wednesday",
            "sender_name": "The MCRcore Team",
            "sender_title": "Business Development",
            "unsubscribe_url": "{{ unsubscribe_url }}",
        }

    def _fill_placeholders(self, template: str, context: Dict) -> str:
        """Simple Jinja2-style placeholder replacement."""
        result = template
        for key, value in context.items():
            placeholder = "{{ " + key + " }}"
            result = result.replace(placeholder, str(value))
            # Also handle no-space variant
            placeholder_nospace = "{{" + key + "}}"
            result = result.replace(placeholder_nospace, str(value))
        return result

    def _build_personalization_prompt(self, filled_template: str, lead_context: Dict) -> str:
        """Build the LLM prompt for personalizing a filled template."""
        context_summary = []
        if lead_context.get("company_name"):
            context_summary.append(f"Company: {lead_context['company_name']}")
        if lead_context.get("industry"):
            context_summary.append(f"Industry: {lead_context['industry']}")
        if lead_context.get("title"):
            context_summary.append(f"Contact Title: {lead_context['title']}")
        if lead_context.get("employee_band"):
            context_summary.append(f"Company Size: {lead_context['employee_band']}")
        if lead_context.get("operational_pain_summary"):
            context_summary.append(f"Known Pain Points: {lead_context['operational_pain_summary']}")
        if lead_context.get("it_pain_points"):
            context_summary.append(f"IT Pain Points: {lead_context['it_pain_points']}")
        if lead_context.get("erp_signals"):
            context_summary.append(f"ERP Context: {lead_context['erp_signals']}")
        if lead_context.get("company_summary"):
            context_summary.append(f"Company Summary: {lead_context['company_summary']}")

        context_str = "\n".join(context_summary) if context_summary else "No additional context available."

        return (
            f"Personalize the following outreach email draft. Make it sound specific "
            f"and informed about the prospect. Reference concrete business context "
            f"where available. Do NOT change the compliance footer or sender info. "
            f"Keep the core value proposition and CTA intact. Remove any remaining "
            f"unfilled placeholders by replacing them with natural language. "
            f"Keep the email under 250 words (body only).\n\n"
            f"PROSPECT CONTEXT:\n{context_str}\n\n"
            f"EMAIL DRAFT:\n{filled_template}\n\n"
            f"Return ONLY the personalized email — no commentary, no subject line prefix, "
            f"no meta-text. Just the email body from greeting to footer."
        )

    def _build_trigger_context(self, lead_data: Dict) -> str:
        """Build trigger event context for 90-day follow-ups."""
        parts = []
        if lead_data.get("operational_pain_summary"):
            parts.append(f"I noticed {{ company_name }} may be dealing with {lead_data['operational_pain_summary'][:100]}.")
        if lead_data.get("infrastructure_signals"):
            parts.append("Infrastructure changes often signal a good time to reassess IT strategy.")
        if not parts:
            parts.append("Heading into a new quarter is often a natural time to reassess IT priorities.")
        return " ".join(parts)

    def _build_new_offer_context(self, lead_data: Dict) -> str:
        """Build new offer context for 90-day follow-ups."""
        pkg_key = self._normalize_package_key(lead_data.get("recommended_offer", ""))
        pkg_block = PACKAGE_BLOCKS.get(pkg_key, {})
        if pkg_block:
            return f"We've expanded our {pkg_block.get('name', 'services')} offering — {pkg_block.get('value_prop', '')[:150]}"
        return "We've expanded our service offerings this quarter and I wanted to make sure you knew about the options available."

    # -----------------------------------------------------------------
    # Private Helpers — Outreach Event Creation
    # -----------------------------------------------------------------

    def _create_outreach_event(
        self,
        lead_id: str,
        result: Dict,
        stage: str,
        session,
    ) -> Optional[str]:
        """Create an OutreachEvent record in the database."""
        try:
            from db.repositories import OutreachRepository
            repo = OutreachRepository(session)
            event = repo.create(
                lead_id=lead_id,
                stage=stage,
                package_angle=result.get("package_angle", ""),
                subject=result.get("subject", ""),
                body_hash=result.get("body_hash", ""),
                delivery_status="draft",
                compliance_passed=True,
            )
            session.flush()
            return event.outreach_id
        except Exception as e:
            self.logger.error(f"Failed to create OutreachEvent: {e}")
            return None
