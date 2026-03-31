"""
MCRcore Growth Engine - Migration 001: Initial Schema

Creates all tables for the growth engine pipeline.
Designed to be run standalone or imported by a migration runner.

Usage:
    python -m db.migrations.001_initial          # forward
    python -m db.migrations.001_initial rollback  # rollback
"""

import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import text
from db.database import engine, init_db, drop_db

MIGRATION_ID = "001_initial"
DESCRIPTION = "Create all initial tables for MCRcore Growth Engine"

# Full DDL listed here for documentation / auditability.
# In practice init_db() delegates to SQLAlchemy's create_all which is
# idempotent and derives DDL from models.py.

TABLES = [
    "companies",
    "contacts",
    "sources",
    "leads",
    "enrichment_profiles",
    "signal_profiles",
    "score_snapshots",
    "outreach_events",
    "reply_events",
    "opportunities",
    "suppression_records",
    "audit_events",
    "workflow_jobs",
    "nurture_schedules",
]


def upgrade() -> None:
    """Apply migration: create all tables and indexes."""
    print(f"[{MIGRATION_ID}] Applying migration: {DESCRIPTION}")
    init_db()

    # Verify all tables exist
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
            existing = {row[0] for row in result}
        else:
            from sqlalchemy import inspect
            inspector = inspect(engine)
            existing = set(inspector.get_table_names())

    missing = [t for t in TABLES if t not in existing]
    if missing:
        print(f"[{MIGRATION_ID}] WARNING: missing tables after migration: {missing}")
    else:
        print(f"[{MIGRATION_ID}] All {len(TABLES)} tables created successfully.")

    # Record migration in a simple tracking table
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS _migrations ("
            "  migration_id TEXT PRIMARY KEY,"
            "  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))
        conn.execute(
            text("INSERT OR IGNORE INTO _migrations (migration_id) VALUES (:mid)"),
            {"mid": MIGRATION_ID},
        )
        conn.commit()
    print(f"[{MIGRATION_ID}] Migration recorded.")


def downgrade() -> None:
    """Rollback migration: drop all tables."""
    print(f"[{MIGRATION_ID}] Rolling back migration: {DESCRIPTION}")
    drop_db()
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS _migrations"))
        conn.commit()
    print(f"[{MIGRATION_ID}] All tables dropped.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        downgrade()
    else:
        upgrade()
