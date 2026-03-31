"""
MCRcore Growth Engine - ERP and Industry Signal Agent

Analyzes enrichment text, website content, and profile signals to
detect ERP system usage and industry relevance.  Produces a
SignalProfile with per-signal confidence floats (0.0 - 1.0).

Detected ERP signals:
    - Epicor Prophet 21 (epicor_signal)
    - Point of Rental    (por_signal)
    - McLeod Software    (mcleod_signal)
    - DAT Keypoint       (dat_keypoint_signal)

Detected industry signals:
    - Manufacturing      (manufacturing_signal)
    - Freight/Logistics  (logistics_signal)
    - Insurance          (insurance_signal)
    - Scaling SMB        (scaling_signal)
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.skills.erp_signal_detection import (
    calculate_weighted_evidence,
    get_confidence_label,
    get_erp_keywords,
    get_industry_keywords,
)
from src.utils import llm_client
from db.repositories import (
    EnrichmentRepository,
    LeadRepository,
    CompanyRepository,
    SignalRepository,
)


class ERPSignalAgent(BaseAgent):
    """
    Detects ERP-system and industry-relevance signals for a lead.

    Uses a two-pass approach:
        1. Keyword matching (fast, deterministic).
        2. LLM classification (slower, nuanced) — blended in when the
           keyword pass is ambiguous.
    """

    def __init__(self, session: Session):
        super().__init__(
            name="erp-signal-agent",
            description="Detects ERP and industry signals from enrichment data",
        )
        self.session = session
        self.lead_repo = LeadRepository(session)
        self.company_repo = CompanyRepository(session)
        self.enrichment_repo = EnrichmentRepository(session)
        self.signal_repo = SignalRepository(session)

        # Load keyword registries once
        self._erp_keywords = get_erp_keywords()
        self._industry_keywords = get_industry_keywords()

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def run(self, lead_id: str, **kwargs) -> Dict[str, Any]:
        """Primary entry point — alias for detect_signals()."""
        return self.detect_signals(lead_id)

    # ------------------------------------------------------------------
    # Core public methods
    # ------------------------------------------------------------------

    def detect_signals(self, lead_id: str) -> Dict[str, Any]:
        """
        Full signal-detection pipeline for a single lead.

        Steps:
            1. Load lead, company, and latest enrichment profile.
            2. Build a text corpus from all available data.
            3. Run keyword scanning for ERP and industry signals.
            4. Run LLM classification for ambiguous signals.
            5. Blend scores and store SignalProfile.

        Returns:
            Dict with signal_id, all signal scores, and confidence labels.
        """
        self.log_action("detect_start", f"Signal detection for lead {lead_id}")

        lead = self.lead_repo.get_by_id(lead_id)
        if lead is None:
            self.log_action("detect_fail", f"Lead {lead_id} not found", status="failure")
            return {"error": "lead_not_found", "lead_id": lead_id}

        # Gather text corpus
        corpus = self._build_corpus(lead)

        # --- Pass 1: keyword matching ---
        erp_matches = self.scan_for_erp(corpus)
        industry_matches, company_data = self.scan_for_industry(
            corpus,
            self._get_company_data(lead),
        )

        # Calculate keyword-based scores
        erp_scores = self.calculate_signal_confidence(erp_matches, self._erp_keywords)
        industry_scores = self.calculate_signal_confidence(industry_matches, self._industry_keywords)

        # --- Pass 2: LLM classification (when keyword signals are weak) ---
        llm_scores = self._llm_classify_signals(corpus, erp_scores, industry_scores)

        # --- Blend keyword + LLM scores ---
        final_erp = self._blend_scores(erp_scores, llm_scores, list(self._erp_keywords.keys()))
        final_industry = self._blend_scores(industry_scores, llm_scores, list(self._industry_keywords.keys()))

        # --- Map to DB column names ---
        signal_data = {
            "epicor_signal": final_erp.get("epicor", 0.0),
            "por_signal": final_erp.get("por", 0.0),
            "mcleod_signal": final_erp.get("mcleod", 0.0),
            "dat_keypoint_signal": final_erp.get("dat_keypoint", 0.0),
            "manufacturing_signal": final_industry.get("manufacturing", 0.0),
            "logistics_signal": final_industry.get("logistics", 0.0),
            "insurance_signal": final_industry.get("insurance", 0.0),
            "scaling_signal": final_industry.get("scaling", 0.0),
        }

        # Clamp all values to 0.0-1.0
        for key in signal_data:
            signal_data[key] = round(max(0.0, min(1.0, signal_data[key])), 3)

        # --- Persist SignalProfile ---
        existing = self.signal_repo.get_by_lead(lead_id)
        if existing:
            self.signal_repo.update(existing.signal_id, **signal_data)
            signal_id = existing.signal_id
        else:
            sp = self.signal_repo.create(lead_id=lead_id, **signal_data)
            signal_id = sp.signal_id

        self.session.commit()

        # Build result with labels
        result = {
            "signal_id": signal_id,
            "lead_id": lead_id,
        }
        for key, value in signal_data.items():
            result[key] = value
            result[f"{key}_label"] = get_confidence_label(value)

        self.log_action(
            "detect_complete",
            f"Signal detection complete for lead {lead_id}",
            metadata=signal_data,
        )

        return result

    def scan_for_erp(self, text: str) -> Dict[str, List[str]]:
        """
        Scan text for ERP-system keyword matches.

        Args:
            text: Combined text corpus (already lowercased).

        Returns:
            {erp_key: [matched_keywords, ...]}
        """
        matches: Dict[str, List[str]] = {}
        text_lower = text.lower()

        for erp_key, erp_info in self._erp_keywords.items():
            found = []
            for kw in erp_info["keywords"]:
                if kw.lower() in text_lower:
                    found.append(kw)
            if found:
                matches[erp_key] = found

        return matches

    def scan_for_industry(
        self,
        text: str,
        company_data: Dict[str, Any],
    ) -> Tuple[Dict[str, List[str]], Dict[str, Any]]:
        """
        Scan text and company data for industry-relevance keyword matches.

        Args:
            text: Combined text corpus.
            company_data: Company metadata dict.

        Returns:
            (matches_dict, enriched_company_data)
        """
        matches: Dict[str, List[str]] = {}
        # Combine text with company metadata
        combined = text.lower()
        for field in ("industry", "summary", "company_name"):
            val = company_data.get(field)
            if val:
                combined += " " + str(val).lower()

        for ind_key, ind_info in self._industry_keywords.items():
            found = []
            for kw in ind_info["keywords"]:
                if kw.lower() in combined:
                    found.append(kw)
            if found:
                matches[ind_key] = found

        return matches, company_data

    def calculate_signal_confidence(
        self,
        matches: Dict[str, List[str]],
        keyword_registry: Dict[str, Dict] = None,
    ) -> Dict[str, float]:
        """
        Convert keyword matches into confidence scores using the
        weighted-evidence algorithm from the erp_signal_detection skill.

        Args:
            matches: {signal_key: [matched_keywords]}
            keyword_registry: Keyword registry to use for weights.

        Returns:
            {signal_key: confidence_float}
        """
        return calculate_weighted_evidence(matches, keyword_registry)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_corpus(self, lead) -> str:
        """
        Assemble all available text for a lead into a single string.
        Pulls from company data, enrichment profile, and contact info.
        """
        parts: List[str] = []

        # Company data
        if lead.company_id:
            company = self.company_repo.get_by_id(lead.company_id)
            if company:
                for attr in ("company_name", "industry", "summary", "domain", "geography"):
                    val = getattr(company, attr, None)
                    if val:
                        parts.append(str(val))

        # Enrichment profile
        enrichment = self.enrichment_repo.get_by_lead(lead.lead_id)
        if enrichment:
            for attr in ("company_summary", "operational_pain_summary", "it_pain_points",
                         "erp_signals", "compliance_signals", "remote_work_signals",
                         "infrastructure_signals"):
                val = getattr(enrichment, attr, None)
                if val:
                    parts.append(str(val))
            # Parse evidence_json for extra text
            if enrichment.evidence_json:
                try:
                    evidence = json.loads(enrichment.evidence_json)
                    parts.append(json.dumps(evidence, default=str))
                except (json.JSONDecodeError, TypeError):
                    pass

        # Contact info
        if lead.contact_id:
            contact_repo = __import__(
                "db.repositories", fromlist=["ContactRepository"]
            ).ContactRepository(self.session)
            contact = contact_repo.get_by_id(lead.contact_id)
            if contact:
                if contact.title:
                    parts.append(contact.title)
                if contact.full_name:
                    parts.append(contact.full_name)

        return " ".join(parts)

    def _get_company_data(self, lead) -> Dict[str, Any]:
        """Extract company data dict from a lead."""
        if not lead.company_id:
            return {}
        company = self.company_repo.get_by_id(lead.company_id)
        if not company:
            return {}
        return {
            "company_name": company.company_name,
            "domain": company.domain,
            "industry": company.industry,
            "employee_band": company.employee_band,
            "geography": company.geography,
            "summary": company.summary,
        }

    def _llm_classify_signals(
        self,
        corpus: str,
        erp_scores: Dict[str, float],
        industry_scores: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Use LLM classification when keyword-only scores are ambiguous
        (between 0.1 and 0.6).  If keyword scores are already high or
        zero, skip the LLM call to save cost.

        Returns:
            Dict of signal_key -> llm_confidence for all signals
            that were classified.
        """
        # Identify ambiguous signals
        all_scores = {**erp_scores, **industry_scores}
        ambiguous = {k: v for k, v in all_scores.items() if 0.05 < v < 0.6}

        # Also classify any signal with zero keyword hits if corpus is non-trivial
        if len(corpus) > 100:
            all_keys = list(self._erp_keywords.keys()) + list(self._industry_keywords.keys())
            for key in all_keys:
                if key not in all_scores:
                    ambiguous[key] = 0.0

        if not ambiguous:
            return {}

        # Build category list for LLM
        categories = []
        label_map = {}
        for key in ambiguous:
            reg = self._erp_keywords.get(key) or self._industry_keywords.get(key)
            label = reg["label"] if reg else key
            categories.append(label)
            label_map[label] = key

        # Truncate corpus for LLM
        truncated = corpus[:3000] if len(corpus) > 3000 else corpus

        try:
            llm_result = llm_client.classify_text(
                text=truncated,
                categories=categories,
            )
            # Map labels back to signal keys
            mapped: Dict[str, float] = {}
            for label, confidence in llm_result.items():
                key = label_map.get(label)
                if key:
                    mapped[key] = float(confidence)
            return mapped
        except Exception as exc:
            self.log_action(
                "llm_classify_fail",
                f"LLM classification failed: {exc}",
                status="failure",
            )
            return {}

    def _blend_scores(
        self,
        keyword_scores: Dict[str, float],
        llm_scores: Dict[str, float],
        all_keys: List[str],
    ) -> Dict[str, float]:
        """
        Blend keyword-based and LLM-based scores.

        Strategy:
            - If keyword score >= 0.6, trust keywords (weight 0.8 kw + 0.2 llm)
            - If keyword score < 0.6 and LLM available, weight 0.4 kw + 0.6 llm
            - If only one source available, use that source directly.
        """
        blended: Dict[str, float] = {}

        for key in all_keys:
            kw_score = keyword_scores.get(key, 0.0)
            llm_score = llm_scores.get(key)

            if llm_score is None:
                blended[key] = kw_score
            elif kw_score >= 0.6:
                # High keyword confidence — trust keywords more
                blended[key] = kw_score * 0.8 + llm_score * 0.2
            else:
                # Low/ambiguous keyword — lean on LLM
                blended[key] = kw_score * 0.4 + llm_score * 0.6

        return blended
