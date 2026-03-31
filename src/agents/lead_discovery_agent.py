"""
MCRcore Growth Engine - Lead Discovery Agent

Searches approved sources for new leads matching the Ideal Customer
Profile (ICP).  Normalizes raw data into Company + Contact + Lead
records, tags service-fit flags, assigns source provenance, and runs
dedup checks before insert.

Target throughput: 50 new leads per day.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from config.icp_rules import (
    COMPANY_SIZE_BANDS,
    EXCLUSION_RULES,
    TARGET_INDUSTRIES,
    TITLE_PATTERNS,
    TITLE_PRIORITY_MAP,
    SizeBand,
)
from config.geo_routing import get_geo_zone, get_eligible_services, MIDWEST_STATE_CODES
from config.service_catalog import SERVICES
from config.source_policy import APPROVED_SOURCES
from db.repositories import (
    AuditRepository,
    CompanyRepository,
    ContactRepository,
    LeadRepository,
    SourceRepository,
    SuppressionRepository,
)
from src.agents.base_agent import BaseAgent
from src.agents.source_compliance_agent import SourceComplianceAgent
from src.utils.dedup import generate_duplicate_hash


# Daily lead target
DAILY_LEAD_TARGET = 50


class LeadDiscoveryAgent(BaseAgent):
    """
    Discovers, normalizes, deduplicates, and inserts new leads from
    approved sources into the Growth Engine pipeline.
    """

    def __init__(self, session: Session):
        super().__init__(
            name="LeadDiscoveryAgent",
            description=(
                "Discovers new leads from CSV, inbound forms, referrals, "
                "and API sources.  Normalizes, deduplicates, tags ICP fit, "
                f"and targets {DAILY_LEAD_TARGET} new leads per day."
            ),
        )
        self.session = session

        # Repositories
        self.lead_repo = LeadRepository(session)
        self.company_repo = CompanyRepository(session)
        self.contact_repo = ContactRepository(session)
        self.source_repo = SourceRepository(session)
        self.suppression_repo = SuppressionRepository(session)
        self.audit_repo = AuditRepository(session)

        # Sibling agent for compliance checks
        self.compliance_agent = SourceComplianceAgent(session)

        # Session counters
        self._leads_created_today = 0

    # ------------------------------------------------------------------
    # run() - abstract method implementation
    # ------------------------------------------------------------------
    def run(self, *args, **kwargs) -> Dict[str, Any]:
        """Return agent stats and today's creation count."""
        stats = self.get_stats()
        stats["leads_created_today"] = self._leads_created_today
        stats["daily_target"] = DAILY_LEAD_TARGET
        return stats

    # ==================================================================
    # PUBLIC DISCOVERY METHODS
    # ==================================================================

    def discover_from_csv(self, filepath: str) -> Dict[str, Any]:
        """
        Discover leads from a CSV file.

        The CSV import service (csv_importer) handles parsing; this
        method is the agent-level orchestrator that coordinates
        compliance, dedup, and record creation for each row.

        Args:
            filepath: Path to the CSV file.

        Returns:
            Summary dict with imported/skipped/error counts.
        """
        # Lazy import to avoid circular dependency
        from src.services.csv_importer import CSVImporter

        self.log_action(
            "discover_csv_start",
            f"Starting CSV discovery from '{filepath}'",
            metadata={"filepath": filepath},
        )

        importer = CSVImporter(self.session, self)
        result = importer.import_file(filepath)

        self.log_action(
            "discover_csv_complete",
            (
                f"CSV import complete: {result['imported']} imported, "
                f"{result['skipped']} skipped, {result['errors']} errors"
            ),
            status="success" if result["errors"] == 0 else "warning",
            metadata=result,
        )
        return result

    def discover_from_inbound(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an inbound website form submission as a new lead.

        Args:
            form_data: Dict with keys:
                company_name, domain, industry, employee_count,
                contact_name, contact_title, contact_email, geography,
                message (optional)

        Returns:
            Result dict with lead_id or skip/error reason.
        """
        self.log_action(
            "discover_inbound",
            f"Processing inbound form for '{form_data.get('company_name', 'unknown')}'",
            metadata={"source": "mcrcore_inbound"},
        )

        return self._process_single_lead(
            raw_data=form_data,
            source_name="mcrcore_inbound",
            source_type="inbound",
        )

    def discover_from_referral(self, referral_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a referral lead (e.g. Tallman Equipment Group).

        Referral leads receive boosted priority.

        Args:
            referral_data: Dict with lead fields plus:
                referrer_name, referrer_company (optional)

        Returns:
            Result dict with lead_id or skip/error reason.
        """
        referrer = referral_data.get("referrer_company", "unknown")
        source_name = referral_data.get("source_name", "tallman_referrals")

        self.log_action(
            "discover_referral",
            f"Processing referral from '{referrer}'",
            metadata={"referrer": referrer, "source_name": source_name},
        )

        result = self._process_single_lead(
            raw_data=referral_data,
            source_name=source_name,
            source_type="referral",
            priority_boost=True,
        )
        return result

    def discover_from_api(
        self, source_name: str, query_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Discover leads from an external API source (Apollo, ZoomInfo, etc.).

        This is a stub that validates the source and processes any
        provided lead records.  Actual API calls would be implemented
        per-provider.

        Args:
            source_name: Approved source identifier (e.g. 'apollo').
            query_params: Dict with 'records' list and optional filters.

        Returns:
            Summary dict with imported/skipped/error counts.
        """
        self.log_action(
            "discover_api_start",
            f"Starting API discovery from '{source_name}'",
            metadata={"source_name": source_name, "params": str(query_params)[:200]},
        )

        # Validate source
        compliance = self.compliance_agent.validate_source(source_name, "prospecting_platform")
        if not compliance["approved"]:
            self.log_action(
                "discover_api_blocked",
                f"Source '{source_name}' not approved: {compliance['reason']}",
                status="failure",
            )
            return {
                "imported": 0,
                "skipped": 0,
                "errors": 0,
                "blocked": True,
                "reason": compliance["reason"],
            }

        # Check rate limits
        policy_entry = APPROVED_SOURCES.get(source_name)
        max_daily = policy_entry.max_daily_pulls if policy_entry else 50
        records = query_params.get("records", [])
        if max_daily and len(records) > max_daily:
            records = records[:max_daily]
            self.log_action(
                "discover_api_rate_limited",
                f"Truncated to {max_daily} records (rate limit for {source_name})",
                status="warning",
            )

        imported = 0
        skipped = 0
        errors = 0

        for raw in records:
            try:
                result = self._process_single_lead(
                    raw_data=raw,
                    source_name=source_name,
                    source_type="api",
                )
                if result.get("status") == "created":
                    imported += 1
                elif result.get("status") == "skipped":
                    skipped += 1
                else:
                    errors += 1
            except Exception as exc:
                errors += 1
                self.log_action(
                    "discover_api_row_error",
                    f"Error processing API record: {exc}",
                    status="failure",
                )

        self.log_action(
            "discover_api_complete",
            f"API import from '{source_name}': {imported} imported, {skipped} skipped, {errors} errors",
            metadata={"imported": imported, "skipped": skipped, "errors": errors},
        )
        return {"imported": imported, "skipped": skipped, "errors": errors}

    # ==================================================================
    # CORE PROCESSING PIPELINE
    # ==================================================================

    def _process_single_lead(
        self,
        raw_data: Dict[str, Any],
        source_name: str,
        source_type: str,
        priority_boost: bool = False,
    ) -> Dict[str, Any]:
        """
        Normalize, validate, dedup, and insert a single lead.

        Returns:
            Dict with 'status' ('created', 'skipped', 'error') and details.
        """
        # 1. Normalize
        normalized = self._normalize_lead_data(raw_data)
        company_name = normalized.get("company_name", "")
        domain = normalized.get("domain", "")
        contact_email = normalized.get("contact_email", "")

        # 2. Validate minimum required fields
        if not company_name or not contact_email:
            self.log_action(
                "lead_validation_failed",
                "Missing company_name or contact_email",
                status="skipped",
                metadata=normalized,
            )
            return {"status": "skipped", "reason": "Missing required fields"}

        # 3. Check suppression list
        if contact_email and self.suppression_repo.is_suppressed(contact_email):
            self.log_action(
                "lead_suppressed",
                f"Email '{contact_email}' is on the suppression list",
                status="skipped",
            )
            return {"status": "skipped", "reason": "Email suppressed"}

        # 4. Check domain denylist
        if domain and self.compliance_agent.is_domain_denied(domain):
            self.log_action(
                "lead_domain_denied",
                f"Domain '{domain}' is on the denylist",
                status="skipped",
            )
            return {"status": "skipped", "reason": "Domain on denylist"}

        # 5. Exclusion rules
        exclusion = self._check_exclusions(normalized)
        if exclusion:
            self.log_action(
                "lead_excluded",
                f"Lead excluded: {exclusion}",
                status="skipped",
                metadata={"reason": exclusion},
            )
            return {"status": "skipped", "reason": exclusion}

        # 6. Dedup check
        dup_hash = generate_duplicate_hash(company_name, domain, contact_email)
        existing = self.lead_repo.find_by_duplicate_hash(dup_hash)
        if existing:
            self.log_action(
                "lead_duplicate",
                f"Duplicate lead found (hash={dup_hash[:12]}…)",
                status="skipped",
            )
            return {"status": "skipped", "reason": "Duplicate", "existing_lead_id": existing.lead_id}

        # 7. Source compliance
        compliance = self.compliance_agent.validate_source(source_name, source_type)
        if not compliance["approved"]:
            self.log_action(
                "lead_source_blocked",
                f"Source '{source_name}' not approved",
                status="skipped",
            )
            return {
                "status": "skipped",
                "reason": f"Source not approved: {compliance['reason']}",
            }
        source_record = compliance["source_record"]

        # 8. Create Company (find-or-create by domain)
        company = self._find_or_create_company(normalized)

        # 9. Create Contact (find-or-create by email)
        contact = self._find_or_create_contact(normalized, company.company_id)

        # 10. Tag service-fit
        service_fit = self._tag_service_fit(normalized)

        # 11. Determine recommended offer
        recommended_offer = service_fit.get("top_service", None)
        recommended_cta = self._get_entry_cta(service_fit)

        # 12. Create Lead
        lead = self.lead_repo.create(
            company_id=company.company_id,
            contact_id=contact.contact_id,
            source_id=source_record.source_id if source_record else None,
            status="new",
            substatus="referral_boosted" if priority_boost else "discovered",
            recommended_offer=recommended_offer,
            recommended_entry_cta=recommended_cta,
            owner_agent=self.name,
            duplicate_hash=dup_hash,
        )
        self.session.commit()

        self._leads_created_today += 1

        # Audit
        self.audit_repo.log(
            actor=self.name,
            entity_type="Lead",
            entity_id=lead.lead_id,
            action="create",
            after_json=(
                f'{{"company": "{company_name}", '
                f'"contact": "{contact_email}", '
                f'"source": "{source_name}", '
                f'"recommended_offer": "{recommended_offer}"}}'
            ),
        )
        self.session.commit()

        self.log_action(
            "lead_created",
            (
                f"Lead created: {company_name} / {contact_email} "
                f"(source={source_name}, offer={recommended_offer})"
            ),
            metadata={
                "lead_id": lead.lead_id,
                "company_id": company.company_id,
                "contact_id": contact.contact_id,
                "service_fit": service_fit,
                "priority_boost": priority_boost,
            },
        )

        return {
            "status": "created",
            "lead_id": lead.lead_id,
            "company_id": company.company_id,
            "contact_id": contact.contact_id,
            "recommended_offer": recommended_offer,
            "service_fit": service_fit,
        }

    # ==================================================================
    # NORMALIZATION
    # ==================================================================

    def _normalize_lead_data(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize raw lead data into a consistent dict.

        Handles common variations in key names and cleans values.
        """
        def _clean(val):
            if val is None:
                return ""
            return str(val).strip()

        normalized = {
            "company_name": _clean(raw.get("company_name") or raw.get("company", "")),
            "domain": _clean(raw.get("domain") or raw.get("website", "")).lower().replace("https://", "").replace("http://", "").rstrip("/"),
            "industry": _clean(raw.get("industry", "")),
            "employee_count": raw.get("employee_count") or raw.get("employees") or raw.get("size") or 0,
            "contact_name": _clean(raw.get("contact_name") or raw.get("name", "")),
            "contact_title": _clean(raw.get("contact_title") or raw.get("title", "")),
            "contact_email": _clean(raw.get("contact_email") or raw.get("email", "")).lower(),
            "geography": _clean(raw.get("geography") or raw.get("state") or raw.get("location", "")),
        }

        # Parse employee_count to int
        try:
            ec = normalized["employee_count"]
            if isinstance(ec, str):
                # Handle ranges like "50-200"
                ec = ec.replace(",", "").strip()
                if "-" in ec:
                    parts = ec.split("-")
                    ec = int(parts[0])
                else:
                    ec = int(ec) if ec else 0
            normalized["employee_count"] = int(ec)
        except (ValueError, TypeError):
            normalized["employee_count"] = 0

        # Normalize title via patterns
        normalized["contact_title_normalized"] = self._normalize_title(
            normalized["contact_title"]
        )

        # Determine employee band
        normalized["employee_band"] = self._get_employee_band(
            normalized["employee_count"]
        )

        return normalized

    def _normalize_title(self, title: str) -> str:
        """Map a raw title to a canonical title using TITLE_PATTERNS."""
        if not title:
            return ""
        # Direct match first
        if title in TITLE_PRIORITY_MAP:
            return title
        # Pattern match
        for pattern, canonical in TITLE_PATTERNS:
            if re.search(pattern, title):
                return canonical
        return title

    def _get_employee_band(self, count: int) -> str:
        """Map employee count to a size band string."""
        if count <= 0:
            return "unknown"
        for band, cfg in COMPANY_SIZE_BANDS.items():
            if cfg["min_employees"] <= count <= cfg["max_employees"]:
                return band.value
        if count > 200:
            return "large"
        return "unknown"

    # ==================================================================
    # EXCLUSION CHECKS
    # ==================================================================

    def _check_exclusions(self, normalized: Dict[str, Any]) -> Optional[str]:
        """
        Check ICP exclusion rules.  Returns reason string if excluded,
        None if the lead passes.
        """
        rules = EXCLUSION_RULES

        # Employee count bounds
        emp = normalized.get("employee_count", 0)
        if emp > 0:
            if emp < rules["company_size"]["min_employees"]:
                return f"Company too small ({emp} employees)"
            if emp > rules["company_size"]["max_employees"]:
                return f"Company too large ({emp} employees)"

        # Industry exclusions
        industry = normalized.get("industry", "").lower()
        for excl in rules.get("excluded_industries", []):
            if excl.lower() in industry:
                return f"Excluded industry: {industry}"

        # Title exclusions
        title = normalized.get("contact_title", "")
        for excl_title in rules.get("excluded_titles", []):
            if excl_title.lower() in title.lower():
                return f"Excluded title: {title}"

        # Company denylist
        company = normalized.get("company_name", "")
        for denied_company in rules.get("company_denylist", []):
            if denied_company.lower() in company.lower():
                return f"Company on denylist: {company}"

        # Email domain denylist
        email = normalized.get("contact_email", "")
        if "@" in email:
            email_domain = email.split("@")[1]
            for denied_domain in rules.get("email_domain_denylist", []):
                if email_domain == denied_domain.lower():
                    return f"Personal email domain: {email_domain}"

        return None

    # ==================================================================
    # SERVICE-FIT TAGGING
    # ==================================================================

    def _tag_service_fit(self, normalized: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine candidate service-fit flags based on industry, size,
        and geography.

        Returns a dict:
            {
                "industry_match": str | None,
                "size_band": str,
                "geo_zone": str,
                "eligible_services": [str],
                "top_service": str | None,
                "fit_score_estimate": float,
            }
        """
        industry = normalized.get("industry", "").lower()
        emp_band = normalized.get("employee_band", "unknown")
        geography = normalized.get("geography", "")

        # Industry matching
        matched_industry = None
        industry_bonus = 0
        for ind_key, ind_cfg in TARGET_INDUSTRIES.items():
            keywords = [kw.lower() for kw in ind_cfg.get("keywords", [])]
            if any(kw in industry for kw in keywords):
                matched_industry = ind_key
                industry_bonus = ind_cfg.get("fit_score_bonus", 0)
                break

        # Geo zone
        state_code = geography.upper().strip()[:2] if geography else ""
        geo_zone = get_geo_zone(state_code=state_code)

        # Eligible services for this geography
        eligible = get_eligible_services(state_code=state_code)
        eligible_service_ids = list(eligible.keys())

        # Filter by size band
        size_eligible = []
        for svc_id in eligible_service_ids:
            svc = SERVICES.get(svc_id)
            if svc and emp_band in svc.ideal_size_bands:
                size_eligible.append(svc_id)

        # Pick top service (prefer entry-point services)
        entry_points = ["technical_audit", "essential_cybersecurity", "on_demand_break_fix"]
        top_service = None
        for ep in entry_points:
            if ep in size_eligible:
                top_service = ep
                break
        if not top_service and size_eligible:
            top_service = size_eligible[0]

        # Rough fit score estimate
        base_score = 50
        if matched_industry:
            base_score += industry_bonus
        if emp_band in ("small", "mid"):
            base_score += 15
        elif emp_band == "micro":
            base_score += 10
        if state_code in MIDWEST_STATE_CODES:
            base_score += 10
        fit_score = min(base_score, 100)

        return {
            "industry_match": matched_industry,
            "size_band": emp_band,
            "geo_zone": geo_zone.value,
            "eligible_services": size_eligible,
            "top_service": top_service,
            "fit_score_estimate": fit_score,
        }

    def _get_entry_cta(self, service_fit: Dict[str, Any]) -> str:
        """Determine the recommended entry CTA based on service fit."""
        top = service_fit.get("top_service")
        if not top:
            return "Schedule introductory call"
        svc = SERVICES.get(top)
        if svc:
            return f"Explore {svc.name}"
        return "Schedule introductory call"

    # ==================================================================
    # FIND-OR-CREATE HELPERS
    # ==================================================================

    def _find_or_create_company(self, normalized: Dict[str, Any]):
        """Find existing Company by domain or create a new one."""
        domain = normalized.get("domain", "")
        if domain:
            existing = self.company_repo.find_by_domain(domain)
            if existing:
                return existing

        company = self.company_repo.create(
            company_name=normalized["company_name"],
            domain=domain or None,
            industry=normalized.get("industry", None),
            employee_band=normalized.get("employee_band", None),
            geography=normalized.get("geography", None),
        )
        self.session.flush()
        self.audit_repo.log(
            actor=self.name,
            entity_type="Company",
            entity_id=company.company_id,
            action="create",
            after_json=f'{{"company_name": "{normalized["company_name"]}", "domain": "{domain}"}}',
        )
        return company

    def _find_or_create_contact(self, normalized: Dict[str, Any], company_id: str):
        """Find existing Contact by email or create a new one."""
        email = normalized.get("contact_email", "")
        if email:
            existing = self.contact_repo.find_by_email(email)
            if existing:
                return existing

        title = normalized.get("contact_title_normalized") or normalized.get("contact_title", "")
        title_info = TITLE_PRIORITY_MAP.get(title, {})
        role_priority = title_info.get("priority", 0)

        contact = self.contact_repo.create(
            company_id=company_id,
            full_name=normalized.get("contact_name", "Unknown"),
            title=title,
            email=email or None,
            role_priority=role_priority,
        )
        self.session.flush()
        self.audit_repo.log(
            actor=self.name,
            entity_type="Contact",
            entity_id=contact.contact_id,
            action="create",
            after_json=f'{{"full_name": "{normalized.get("contact_name", "")}", "email": "{email}"}}',
        )
        return contact
