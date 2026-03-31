"""
MCRcore Growth Engine - CSV Import Service

Reads CSV files with lead data, validates and normalizes each row,
routes through the Source Compliance Agent and dedup pipeline, and
creates Company, Contact, and Lead records.

Expected CSV columns:
    company_name, domain, industry, employee_count,
    contact_name, contact_title, contact_email, geography
"""

import csv
import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Session

from src.utils.logger import setup_logger

if TYPE_CHECKING:
    from src.agents.lead_discovery_agent import LeadDiscoveryAgent

logger = setup_logger("mcr_growth_engine.csv_importer")

# Canonical column names (lowercase)
EXPECTED_COLUMNS = {
    "company_name",
    "domain",
    "industry",
    "employee_count",
    "contact_name",
    "contact_title",
    "contact_email",
    "geography",
}

# Column aliases for flexible CSVs
COLUMN_ALIASES = {
    "company": "company_name",
    "company name": "company_name",
    "organization": "company_name",
    "website": "domain",
    "website_url": "domain",
    "url": "domain",
    "vertical": "industry",
    "sector": "industry",
    "employees": "employee_count",
    "size": "employee_count",
    "headcount": "employee_count",
    "name": "contact_name",
    "full_name": "contact_name",
    "contact name": "contact_name",
    "title": "contact_title",
    "job_title": "contact_title",
    "job title": "contact_title",
    "role": "contact_title",
    "email": "contact_email",
    "email_address": "contact_email",
    "contact email": "contact_email",
    "state": "geography",
    "location": "geography",
    "region": "geography",
    "geo": "geography",
}


class CSVImporter:
    """
    Service that reads a CSV file, validates rows, and routes each
    through the LeadDiscoveryAgent's processing pipeline.
    """

    def __init__(self, session: Session, discovery_agent: "LeadDiscoveryAgent"):
        """
        Args:
            session: SQLAlchemy session for DB access.
            discovery_agent: The LeadDiscoveryAgent instance to delegate
                             record creation and compliance checks to.
        """
        self.session = session
        self.agent = discovery_agent
        self.source_name = "csv_import"
        self.source_type = "csv"

    def import_file(
        self,
        filepath: str,
        source_name: str = "csv_import",
        encoding: str = "utf-8",
        delimiter: str = ",",
    ) -> Dict[str, Any]:
        """
        Import a CSV file into the Growth Engine pipeline.

        Args:
            filepath: Absolute or relative path to the CSV file.
            source_name: Source identifier for provenance tracking.
            encoding: File encoding (default utf-8).
            delimiter: CSV delimiter (default comma).

        Returns:
            Summary dict:
                {
                    "filepath": str,
                    "total_rows": int,
                    "imported": int,
                    "skipped": int,
                    "errors": int,
                    "error_details": [{"row": int, "error": str}, ...],
                }
        """
        self.source_name = source_name

        if not os.path.isfile(filepath):
            logger.error(f"CSV file not found: {filepath}")
            return {
                "filepath": filepath,
                "total_rows": 0,
                "imported": 0,
                "skipped": 0,
                "errors": 1,
                "error_details": [{"row": 0, "error": f"File not found: {filepath}"}],
            }

        # Validate source via compliance agent first
        compliance = self.agent.compliance_agent.validate_source(
            source_name, self.source_type
        )
        # CSV import sources are generally safe; allow unless explicitly blocked
        if compliance["risk_level"] == "blocked":
            logger.error(f"Source '{source_name}' is blocked")
            return {
                "filepath": filepath,
                "total_rows": 0,
                "imported": 0,
                "skipped": 0,
                "errors": 1,
                "error_details": [{"row": 0, "error": f"Source blocked: {compliance['reason']}"}],
            }

        # Read and process the CSV
        rows = self._read_csv(filepath, encoding, delimiter)

        total = len(rows)
        imported = 0
        skipped = 0
        errors = 0
        error_details: List[Dict[str, Any]] = []

        for idx, row in enumerate(rows, start=1):
            try:
                # Validate row
                validation = self._validate_row(row, idx)
                if not validation["valid"]:
                    skipped += 1
                    error_details.append({"row": idx, "error": validation["reason"]})
                    logger.debug(f"Row {idx} skipped: {validation['reason']}")
                    continue

                # Normalize column names
                normalized_row = self._normalize_columns(row)

                # Route through discovery agent's processing pipeline
                result = self.agent._process_single_lead(
                    raw_data=normalized_row,
                    source_name=source_name,
                    source_type=self.source_type,
                )

                if result.get("status") == "created":
                    imported += 1
                elif result.get("status") == "skipped":
                    skipped += 1
                    error_details.append({
                        "row": idx,
                        "error": f"Skipped: {result.get('reason', 'unknown')}",
                    })
                else:
                    errors += 1
                    error_details.append({
                        "row": idx,
                        "error": f"Error: {result.get('reason', 'unknown')}",
                    })

            except Exception as exc:
                errors += 1
                error_details.append({"row": idx, "error": str(exc)})
                logger.error(f"Row {idx} error: {exc}")

        summary = {
            "filepath": filepath,
            "source_name": source_name,
            "total_rows": total,
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "error_details": error_details[:50],  # Cap detail list
        }

        logger.info(
            f"CSV import complete: {filepath} — "
            f"{imported}/{total} imported, {skipped} skipped, {errors} errors"
        )
        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_csv(
        self, filepath: str, encoding: str = "utf-8", delimiter: str = ","
    ) -> List[Dict[str, str]]:
        """Read CSV into a list of dicts with lowercased keys."""
        rows = []
        try:
            with open(filepath, "r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    # Lowercase all keys for consistent handling
                    clean_row = {
                        k.strip().lower(): v.strip() if v else ""
                        for k, v in row.items()
                        if k is not None
                    }
                    rows.append(clean_row)
        except Exception as exc:
            logger.error(f"Failed to read CSV '{filepath}': {exc}")
        return rows

    def _normalize_columns(self, row: Dict[str, str]) -> Dict[str, Any]:
        """
        Map CSV column aliases to canonical names.

        Returns a dict with canonical keys.
        """
        normalized = {}
        for raw_key, value in row.items():
            canonical = COLUMN_ALIASES.get(raw_key, raw_key)
            if canonical in EXPECTED_COLUMNS:
                normalized[canonical] = value
        return normalized

    def _validate_row(self, row: Dict[str, str], row_num: int) -> Dict[str, Any]:
        """
        Validate a single CSV row for minimum required fields.

        Returns:
            {"valid": bool, "reason": str}
        """
        # Map to canonical first
        mapped = self._normalize_columns(row)

        company_name = mapped.get("company_name", "").strip()
        contact_email = mapped.get("contact_email", "").strip()

        if not company_name:
            return {"valid": False, "reason": "Missing company_name"}

        if not contact_email:
            return {"valid": False, "reason": "Missing contact_email"}

        # Basic email format check
        if "@" not in contact_email or "." not in contact_email.split("@")[-1]:
            return {"valid": False, "reason": f"Invalid email format: {contact_email}"}

        return {"valid": True, "reason": ""}
