"""
MCRcore Growth Engine - Lead Enrichment Agent

Takes a lead_id, researches the company and contact, and produces an
EnrichmentProfile with:
    - company_summary
    - operational_pain_summary
    - likely IT pain points
    - compliance signals (HIPAA, PCI, SOX, etc.)
    - remote_work_signals
    - infrastructure_signals
    - evidence_json (sources + confidence)
    - research_confidence (0.0 - 1.0)
"""

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.utils import llm_client
from db.repositories import (
    EnrichmentRepository,
    LeadRepository,
    CompanyRepository,
    ContactRepository,
)


# ---------------------------------------------------------------------------
# Compliance / signal keyword banks
# ---------------------------------------------------------------------------

_COMPLIANCE_KEYWORDS: Dict[str, List[str]] = {
    "HIPAA": ["hipaa", "health insurance portability", "phi", "protected health information",
              "healthcare compliance", "medical records"],
    "PCI": ["pci", "pci-dss", "pci dss", "payment card industry", "cardholder data",
            "credit card compliance"],
    "SOX": ["sox", "sarbanes-oxley", "sarbanes oxley", "financial reporting compliance",
            "internal controls"],
    "CMMC": ["cmmc", "cybersecurity maturity", "nist 800-171", "dfars"],
    "SOC2": ["soc2", "soc 2", "service organization control", "trust services criteria"],
    "NIST": ["nist", "nist framework", "nist csf", "nist 800"],
}

_REMOTE_WORK_KEYWORDS: List[str] = [
    "remote", "hybrid", "work from home", "wfh", "distributed team",
    "virtual office", "telecommute", "remote-first", "fully remote",
    "home office", "vpn", "zero trust network access", "ztna",
]

_INFRASTRUCTURE_KEYWORDS: List[str] = [
    "on-prem", "on-premise", "server room", "data center", "colocation",
    "cloud migration", "aws", "azure", "gcp", "legacy server",
    "aging infrastructure", "hardware refresh", "end of life",
    "disaster recovery", "backup", "virtualization", "vmware", "hyper-v",
    "firewall", "switch", "router", "sd-wan", "wan",
]


class LeadEnrichmentAgent(BaseAgent):
    """
    Enrichment agent that researches a lead's company and contact to
    produce structured intelligence stored as an EnrichmentProfile.
    """

    def __init__(self, session: Session):
        super().__init__(
            name="lead-enrichment-agent",
            description="Researches companies and contacts to build enrichment profiles",
        )
        self.session = session
        self.lead_repo = LeadRepository(session)
        self.company_repo = CompanyRepository(session)
        self.contact_repo = ContactRepository(session)
        self.enrichment_repo = EnrichmentRepository(session)

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def run(self, lead_id: str, **kwargs) -> Dict[str, Any]:
        """Primary entry point — alias for enrich_lead()."""
        return self.enrich_lead(lead_id)

    # ------------------------------------------------------------------
    # Core public methods
    # ------------------------------------------------------------------

    def enrich_lead(self, lead_id: str) -> Dict[str, Any]:
        """
        Full enrichment pipeline for a single lead.

        Steps:
            1. Load lead + related company/contact from DB.
            2. Research company (domain, summary, signals).
            3. Research contact (title, role context).
            4. Detect compliance, remote-work, and infrastructure signals.
            5. Generate LLM summaries.
            6. Store EnrichmentProfile.

        Returns:
            Dict with enrichment_id, confidence, and summary data.
        """
        self.log_action("enrich_start", f"Starting enrichment for lead {lead_id}")

        lead = self.lead_repo.get_by_id(lead_id)
        if lead is None:
            self.log_action("enrich_fail", f"Lead {lead_id} not found", status="failure")
            return {"error": "lead_not_found", "lead_id": lead_id}

        company = None
        contact = None
        if lead.company_id:
            company = self.company_repo.get_by_id(lead.company_id)
        if lead.contact_id:
            contact = self.contact_repo.get_by_id(lead.contact_id)

        # Gather raw research data
        raw_data: Dict[str, Any] = {"lead_id": lead_id}
        evidence: List[Dict[str, Any]] = []

        # --- Company research ---
        if company:
            company_research = self.research_company(company.domain or "")
            raw_data["company"] = {
                "name": company.company_name,
                "domain": company.domain,
                "industry": company.industry,
                "employee_band": company.employee_band,
                "geography": company.geography,
                "existing_summary": company.summary,
                "research": company_research,
            }
            evidence.append({
                "source": "company_research",
                "domain": company.domain,
                "data_keys": list(company_research.keys()),
            })
        else:
            raw_data["company"] = None

        # --- Contact research ---
        if contact:
            contact_research = self.research_contact({
                "full_name": contact.full_name,
                "title": contact.title,
                "email": contact.email,
                "profile_url": contact.profile_url,
            })
            raw_data["contact"] = {
                "name": contact.full_name,
                "title": contact.title,
                "email": contact.email,
                "research": contact_research,
            }
            evidence.append({
                "source": "contact_research",
                "name": contact.full_name,
            })
        else:
            raw_data["contact"] = None

        # --- Signal detection ---
        combined_text = self._build_combined_text(raw_data)

        compliance_signals = self._detect_compliance_signals(combined_text)
        remote_signals = self._detect_keyword_signals(combined_text, _REMOTE_WORK_KEYWORDS)
        infra_signals = self._detect_keyword_signals(combined_text, _INFRASTRUCTURE_KEYWORDS)

        raw_data["compliance_signals"] = compliance_signals
        raw_data["remote_work_signals"] = remote_signals
        raw_data["infrastructure_signals"] = infra_signals

        # --- LLM summaries ---
        try:
            summaries = self.generate_summary(raw_data)
            confidence = self._calculate_confidence(raw_data, summaries)
        except Exception as exc:
            self.log_action(
                "llm_summary_fail",
                f"LLM summary generation failed: {exc}",
                status="failure",
            )
            summaries = {
                "company_summary": raw_data.get("company", {}).get("existing_summary") or "",
                "operational_pain_summary": "",
                "it_pain_points": "",
            }
            confidence = max(0.1, self._calculate_confidence(raw_data, summaries) * 0.5)

        # --- Persist EnrichmentProfile ---
        evidence.append({
            "confidence": confidence,
            "signals_found": {
                "compliance": list(compliance_signals.keys()),
                "remote_work": len(remote_signals),
                "infrastructure": len(infra_signals),
            },
        })

        enrichment = self.enrichment_repo.create(
            lead_id=lead_id,
            company_summary=summaries.get("company_summary", ""),
            operational_pain_summary=summaries.get("operational_pain_summary", ""),
            it_pain_points=summaries.get("it_pain_points", ""),
            compliance_signals=json.dumps(compliance_signals),
            remote_work_signals=json.dumps(remote_signals),
            infrastructure_signals=json.dumps(infra_signals),
            evidence_json=json.dumps(evidence, default=str),
            research_confidence=round(confidence, 3),
        )

        # Update lead status
        self.lead_repo.update(
            lead_id,
            status="enriched",
            last_processed_at=datetime.now(timezone.utc),
            owner_agent=self.name,
        )

        self.session.commit()

        self.log_action(
            "enrich_complete",
            f"Enrichment complete for lead {lead_id}, confidence={confidence:.2f}",
            metadata={"enrichment_id": enrichment.enrichment_id, "confidence": confidence},
        )

        return {
            "enrichment_id": enrichment.enrichment_id,
            "lead_id": lead_id,
            "research_confidence": confidence,
            "company_summary": summaries.get("company_summary", ""),
            "operational_pain_summary": summaries.get("operational_pain_summary", ""),
            "it_pain_points": summaries.get("it_pain_points", ""),
            "compliance_signals": compliance_signals,
            "remote_work_signals": remote_signals,
            "infrastructure_signals": infra_signals,
        }

    def research_company(self, domain: str) -> Dict[str, Any]:
        """
        Research a company by its domain.

        In production this would call web-scraping APIs, Clearbit,
        ZoomInfo, etc.  For now it returns structured metadata and
        uses the LLM to infer context from the domain name.

        Returns:
            Dict of research findings.
        """
        if not domain:
            return {"status": "no_domain"}

        self.log_action("research_company", f"Researching domain: {domain}")

        try:
            prompt = (
                f"Given the company domain '{domain}', provide a brief JSON object with:\n"
                f"  company_type: likely type of business\n"
                f"  industry_guess: best guess at industry\n"
                f"  size_guess: likely employee count range\n"
                f"  pain_points: list of 3 likely IT pain points\n"
                f"  tech_signals: list of technologies they likely use\n"
                f"Only output valid JSON."
            )
            response = llm_client.generate_text(
                prompt=prompt,
                system_prompt=(
                    "You are a B2B sales intelligence analyst. "
                    "Infer business characteristics from domain names. "
                    "Return only valid JSON."
                ),
                temperature=0.3,
                max_tokens=512,
            )
            # Parse JSON
            raw = response.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except Exception as exc:
            self.log_action(
                "research_company_fail",
                f"Company research failed for {domain}: {exc}",
                status="failure",
            )
            return {"status": "error", "error": str(exc)}

    def research_contact(self, contact_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Research a contact using available info (name, title, email, profile URL).

        Returns:
            Dict of contact research findings.
        """
        name = contact_info.get("full_name", "")
        title = contact_info.get("title", "")

        if not name and not title:
            return {"status": "insufficient_info"}

        self.log_action("research_contact", f"Researching contact: {name} ({title})")

        try:
            prompt = (
                f"Given this B2B contact:\n"
                f"  Name: {name}\n"
                f"  Title: {title}\n"
                f"  Email: {contact_info.get('email', 'N/A')}\n"
                f"\nProvide a brief JSON object with:\n"
                f"  decision_maker_level: high/medium/low\n"
                f"  likely_buying_role: economic_buyer/technical_buyer/champion/influencer\n"
                f"  communication_style_guess: formal/casual/technical\n"
                f"  engagement_approach: recommended approach for outreach\n"
                f"Only output valid JSON."
            )
            response = llm_client.generate_text(
                prompt=prompt,
                system_prompt=(
                    "You are a B2B sales intelligence analyst. "
                    "Analyze contact information for outreach strategy. "
                    "Return only valid JSON."
                ),
                temperature=0.3,
                max_tokens=512,
            )
            raw = response.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except Exception as exc:
            self.log_action(
                "research_contact_fail",
                f"Contact research failed for {name}: {exc}",
                status="failure",
            )
            return {"status": "error", "error": str(exc)}

    def generate_summary(self, raw_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Use the LLM to generate structured summaries from collected research.

        Returns:
            Dict with keys: company_summary, operational_pain_summary,
            it_pain_points.
        """
        # Build a text block from all available data
        data_text = json.dumps(raw_data, indent=2, default=str)
        # Truncate if excessively long
        if len(data_text) > 6000:
            data_text = data_text[:6000] + "\n... [truncated]"

        prompt = (
            f"Based on the following research data about a potential B2B prospect, "
            f"generate three summaries:\n\n"
            f"1. company_summary: 2-3 sentence overview of the company.\n"
            f"2. operational_pain_summary: Key operational challenges this company "
            f"likely faces that a managed IT provider could solve.\n"
            f"3. it_pain_points: Specific IT infrastructure and technology pain "
            f"points (comma-separated list).\n\n"
            f"Research data:\n{data_text}\n\n"
            f"Return a JSON object with exactly these three keys. Only valid JSON."
        )

        response = llm_client.generate_text(
            prompt=prompt,
            system_prompt=(
                "You are an expert B2B sales analyst for an MSP (managed service provider). "
                "Generate concise, actionable intelligence from research data. "
                "Return only valid JSON."
            ),
            temperature=0.4,
            max_tokens=1024,
        )

        raw = response.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: extract what we can
            result = {
                "company_summary": raw[:500],
                "operational_pain_summary": "",
                "it_pain_points": "",
            }

        # Ensure all required keys exist
        for key in ("company_summary", "operational_pain_summary", "it_pain_points"):
            result.setdefault(key, "")

        self.log_action(
            "generate_summary",
            f"Generated summaries ({len(result.get('company_summary', ''))} chars)",
        )

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_combined_text(self, raw_data: Dict[str, Any]) -> str:
        """Flatten all research data into a single searchable string."""
        parts: List[str] = []

        company = raw_data.get("company")
        if company and isinstance(company, dict):
            for key in ("name", "industry", "existing_summary", "geography"):
                val = company.get(key)
                if val:
                    parts.append(str(val))
            research = company.get("research")
            if isinstance(research, dict):
                parts.append(json.dumps(research, default=str))

        contact = raw_data.get("contact")
        if contact and isinstance(contact, dict):
            for key in ("name", "title"):
                val = contact.get(key)
                if val:
                    parts.append(str(val))
            research = contact.get("research")
            if isinstance(research, dict):
                parts.append(json.dumps(research, default=str))

        return " ".join(parts).lower()

    def _detect_compliance_signals(self, text: str) -> Dict[str, List[str]]:
        """
        Scan text for compliance-related keywords.

        Returns:
            {framework_name: [matched_keywords]} for each framework
            where at least one keyword was found.
        """
        found: Dict[str, List[str]] = {}
        text_lower = text.lower()

        for framework, keywords in _COMPLIANCE_KEYWORDS.items():
            matches = [kw for kw in keywords if kw in text_lower]
            if matches:
                found[framework] = matches

        return found

    def _detect_keyword_signals(self, text: str, keywords: List[str]) -> List[str]:
        """Return list of keywords found in the text."""
        text_lower = text.lower()
        return [kw for kw in keywords if kw in text_lower]

    def _calculate_confidence(
        self,
        raw_data: Dict[str, Any],
        summaries: Dict[str, str],
    ) -> float:
        """
        Calculate a research_confidence score (0.0-1.0) based on
        how much data we actually gathered.
        """
        score = 0.0
        max_score = 0.0

        # Company data available
        max_score += 0.3
        company = raw_data.get("company")
        if company and isinstance(company, dict):
            if company.get("name"):
                score += 0.1
            if company.get("industry"):
                score += 0.05
            if company.get("domain"):
                score += 0.05
            research = company.get("research", {})
            if isinstance(research, dict) and research.get("status") != "error":
                score += 0.1

        # Contact data available
        max_score += 0.2
        contact = raw_data.get("contact")
        if contact and isinstance(contact, dict):
            if contact.get("name"):
                score += 0.08
            if contact.get("title"):
                score += 0.07
            research = contact.get("research", {})
            if isinstance(research, dict) and research.get("status") != "error":
                score += 0.05

        # Summaries generated
        max_score += 0.3
        if summaries.get("company_summary"):
            score += 0.15
        if summaries.get("operational_pain_summary"):
            score += 0.1
        if summaries.get("it_pain_points"):
            score += 0.05

        # Signals detected
        max_score += 0.2
        if raw_data.get("compliance_signals"):
            score += 0.08
        if raw_data.get("remote_work_signals"):
            score += 0.06
        if raw_data.get("infrastructure_signals"):
            score += 0.06

        return min(score, 1.0)
