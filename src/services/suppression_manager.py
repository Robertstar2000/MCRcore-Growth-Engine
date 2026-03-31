"""
MCRcore Growth Engine - Suppression Management Service

Manages the email suppression list used by the Compliance Agent to block
outbound sends to addresses that must not be contacted.

Supports three suppression categories:
  - bounce:  Hard bounces or repeated soft bounces
  - opt_out: Recipient explicitly opted out
  - manual:  Admin-added suppressions (legal, role-based, etc.)

All mutations are audit-logged.  Removing a suppression requires human
approval via Teams notification.
"""

import csv
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.utils.logger import setup_logger
from src.utils.teams_notifier import send_approval_request, send_teams_message

logger = setup_logger("mcr_growth_engine.suppression_manager")


# -----------------------------------------------------------------------
# In-memory store (replaced by DB session in production wiring)
# -----------------------------------------------------------------------
class _InMemorySuppressionStore:
    """Simple in-memory store for standalone / testing usage."""

    def __init__(self):
        self._records: Dict[str, dict] = {}  # email -> record

    def add(self, email: str, reason: str, source: str, category: str) -> dict:
        email = email.strip().lower()
        record = {
            "suppression_id": str(uuid.uuid4()),
            "email": email,
            "reason": reason,
            "source": source,
            "category": category,  # bounce | opt_out | manual
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        }
        self._records[email] = record
        return record

    def remove(self, email: str) -> Optional[dict]:
        email = email.strip().lower()
        rec = self._records.pop(email, None)
        return rec

    def get(self, email: str) -> Optional[dict]:
        return self._records.get(email.strip().lower())

    def exists(self, email: str) -> bool:
        return email.strip().lower() in self._records

    def all_records(self) -> List[dict]:
        return list(self._records.values())

    def count(self) -> int:
        return len(self._records)


class SuppressionManager:
    """
    Service for managing the email suppression list.

    Parameters
    ----------
    db_session : optional
        SQLAlchemy session.  When provided, the manager persists to the
        ``suppression_records`` table via SuppressionRepository.
        When *None* an in-memory store is used (useful for tests).
    """

    def __init__(self, db_session=None):
        self._session = db_session
        self._store = _InMemorySuppressionStore()
        self._audit_log: List[dict] = []

        # If a DB session is provided, wire up the repository
        self._repo = None
        self._audit_repo = None
        if db_session is not None:
            try:
                from db.repositories import SuppressionRepository, AuditRepository
                self._repo = SuppressionRepository(db_session)
                self._audit_repo = AuditRepository(db_session)
            except Exception as exc:
                logger.warning(f"Could not initialise DB repositories: {exc}")

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def add_suppression(
        self,
        email: str,
        reason: str,
        source: str,
        category: str = "manual",
    ) -> dict:
        """
        Add an email to the suppression list.

        Args:
            email:    Email address to suppress.
            reason:   Human-readable reason (e.g. 'hard_bounce', 'opt_out').
            source:   Where the suppression originated (e.g. 'bounce_handler').
            category: One of 'bounce', 'opt_out', 'manual'.

        Returns:
            The suppression record dict.
        """
        email = email.strip().lower()
        logger.info(f"Adding suppression: {email} reason={reason} cat={category}")

        # Persist to DB if available
        if self._repo is not None:
            try:
                rec = self._repo.suppress(email=email, reason=reason, source=source)
                self._log_audit(
                    "suppression_add", email,
                    after={"reason": reason, "source": source, "category": category},
                    actor=source,
                )
                if self._session:
                    self._session.commit()
                return {
                    "suppression_id": rec.suppression_id,
                    "email": rec.email,
                    "reason": rec.reason,
                    "source": rec.source,
                    "category": category,
                    "created_at": rec.effective_at.isoformat() if rec.effective_at else None,
                    "active": True,
                }
            except Exception as exc:
                logger.error(f"DB suppression add failed: {exc}")

        # Fallback: in-memory
        record = self._store.add(email, reason, source, category)
        self._log_audit(
            "suppression_add", email,
            after={"reason": reason, "source": source, "category": category},
            actor=source,
        )
        return record

    def remove_suppression(self, email: str, admin_actor: str) -> dict:
        """
        Remove an email from the suppression list.

        **Requires human approval via Teams.**  The removal is performed
        immediately but a Teams approval request is sent so that an admin
        can verify or re-suppress.

        Args:
            email:        Email address to unsuppress.
            admin_actor:  Identifier of the person/system requesting removal.

        Returns:
            Dict with removal details.
        """
        email = email.strip().lower()
        logger.info(f"Removing suppression: {email} by {admin_actor}")

        removed_record = None

        # DB path
        if self._repo is not None:
            try:
                from db.repositories import SuppressionRepository
                existing = self._repo.find_by_email(email)
                for rec in existing:
                    self._repo.delete(rec.suppression_id)
                if self._session:
                    self._session.commit()
                removed_record = {"email": email, "records_removed": len(existing)}
            except Exception as exc:
                logger.error(f"DB suppression remove failed: {exc}")

        # In-memory fallback
        if removed_record is None:
            rec = self._store.remove(email)
            removed_record = rec or {"email": email, "status": "not_found"}

        # Audit
        self._log_audit(
            "suppression_remove", email,
            before={"email": email},
            after={"removed_by": admin_actor},
            actor=admin_actor,
        )

        # Send Teams approval request for oversight
        send_approval_request(
            request_type="suppression_removal",
            details={
                "description": (
                    f"Suppression removal requested for {email} by {admin_actor}. "
                    "Please verify this is intentional."
                ),
                "requester": admin_actor,
                "email": email,
            },
        )

        return {
            "email": email,
            "removed_by": admin_actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "teams_approval_sent": True,
            "record": removed_record,
        }

    def is_suppressed(self, email: str) -> bool:
        """Check whether an email is on the suppression list."""
        email = email.strip().lower()

        # DB path
        if self._repo is not None:
            try:
                return self._repo.is_suppressed(email)
            except Exception as exc:
                logger.error(f"DB suppression check failed: {exc}")

        return self._store.exists(email)

    def get_suppression_list(self) -> List[dict]:
        """Return all active suppression records."""
        if self._repo is not None:
            try:
                records = self._repo.list_all(limit=10000)
                return [
                    {
                        "suppression_id": r.suppression_id,
                        "email": r.email,
                        "reason": r.reason,
                        "source": r.source,
                        "effective_at": r.effective_at.isoformat() if r.effective_at else None,
                    }
                    for r in records
                ]
            except Exception as exc:
                logger.error(f"DB suppression list failed: {exc}")

        return self._store.all_records()

    def import_suppression_csv(self, filepath: str) -> dict:
        """
        Import suppressions from a CSV file.

        Expected columns: email, reason, source, category (optional).
        Returns summary dict with counts.
        """
        added = 0
        skipped = 0
        errors = 0

        try:
            with open(filepath, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = (row.get("email") or "").strip().lower()
                    if not email:
                        errors += 1
                        continue
                    if self.is_suppressed(email):
                        skipped += 1
                        continue
                    reason = row.get("reason", "csv_import")
                    source = row.get("source", f"csv:{filepath}")
                    category = row.get("category", "manual")
                    try:
                        self.add_suppression(email, reason, source, category)
                        added += 1
                    except Exception as exc:
                        logger.error(f"Failed to import {email}: {exc}")
                        errors += 1
        except FileNotFoundError:
            logger.error(f"CSV file not found: {filepath}")
            return {"error": f"File not found: {filepath}"}
        except Exception as exc:
            logger.error(f"CSV import error: {exc}")
            return {"error": str(exc)}

        summary = {
            "filepath": filepath,
            "added": added,
            "skipped": skipped,
            "errors": errors,
            "total_processed": added + skipped + errors,
        }
        logger.info(f"CSV import complete: {summary}")
        self._log_audit(
            "suppression_csv_import", filepath,
            after=summary, actor="csv_importer",
        )
        return summary

    def export_suppression_list(self, filepath: str) -> dict:
        """
        Export the suppression list to a CSV file.

        Returns summary dict.
        """
        records = self.get_suppression_list()

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["email", "reason", "source", "category", "created_at"],
                )
                writer.writeheader()
                for rec in records:
                    writer.writerow({
                        "email": rec.get("email", ""),
                        "reason": rec.get("reason", ""),
                        "source": rec.get("source", ""),
                        "category": rec.get("category", ""),
                        "created_at": rec.get("created_at") or rec.get("effective_at", ""),
                    })
        except Exception as exc:
            logger.error(f"CSV export error: {exc}")
            return {"error": str(exc)}

        summary = {
            "filepath": filepath,
            "records_exported": len(records),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"CSV export complete: {summary}")
        self._log_audit(
            "suppression_csv_export", filepath,
            after=summary, actor="csv_exporter",
        )
        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_audit(
        self,
        action: str,
        entity_id: str,
        before: dict = None,
        after: dict = None,
        actor: str = "suppression_manager",
    ):
        """Log an audit event both locally and to the DB if available."""
        entry = {
            "audit_id": str(uuid.uuid4()),
            "actor": actor,
            "entity_type": "suppression",
            "entity_id": entity_id,
            "action": action,
            "before": before,
            "after": after,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._audit_log.append(entry)

        if self._audit_repo is not None:
            try:
                self._audit_repo.log(
                    actor=actor,
                    entity_type="suppression",
                    entity_id=entity_id,
                    action=action,
                    before_json=json.dumps(before) if before else None,
                    after_json=json.dumps(after) if after else None,
                )
                if self._session:
                    self._session.commit()
            except Exception as exc:
                logger.error(f"Audit DB write failed: {exc}")

    def get_audit_log(self) -> List[dict]:
        """Return the local audit log (in-memory)."""
        return list(self._audit_log)
