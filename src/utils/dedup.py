"""
MCRcore Growth Engine - Deduplication Utilities

Generates deterministic hashes from lead/company data and checks
for duplicates against the database.
"""

import hashlib
import os
from typing import Optional

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from src.utils.logger import setup_logger

load_dotenv()

logger = setup_logger("mcr_growth_engine.dedup")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///mcr_growth_engine.db")


def generate_duplicate_hash(
    company_name: str,
    domain: str,
    contact_email: str,
) -> str:
    """
    Generate a deterministic SHA-256 hash from normalized lead fields.

    The hash is built from: company_name + domain + contact_email,
    all lowercased and stripped of whitespace.

    Args:
        company_name: Company / organization name.
        domain: Company website domain (e.g. example.com).
        contact_email: Primary contact email address.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    normalized = "|".join([
        (company_name or "").strip().lower(),
        (domain or "").strip().lower(),
        (contact_email or "").strip().lower(),
    ])
    hash_value = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    logger.debug(
        f"Generated dedup hash for '{company_name}': {hash_value[:12]}..."
    )
    return hash_value


def check_duplicate(
    dedup_hash: str,
    table_name: str = "leads",
    hash_column: str = "dedup_hash",
    db_url: str = None,
) -> Optional[dict]:
    """
    Check whether a record with the given dedup hash already exists.

    Args:
        dedup_hash: The SHA-256 hash to look up.
        table_name: Database table to query (default: 'leads').
        hash_column: Column that stores the dedup hash.
        db_url: Database connection URL. Defaults to DATABASE_URL env var.

    Returns:
        A dict with the existing row data if duplicate found, else None.
    """
    db_url = db_url or DATABASE_URL
    engine = create_engine(db_url)

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT * FROM {table_name} WHERE {hash_column} = :hash LIMIT 1"),
                {"hash": dedup_hash},
            )
            row = result.mappings().first()
            if row:
                logger.info(f"Duplicate found for hash {dedup_hash[:12]}...")
                return dict(row)
            logger.debug(f"No duplicate for hash {dedup_hash[:12]}...")
            return None
    except Exception as e:
        logger.warning(f"Dedup check failed (table may not exist yet): {e}")
        return None
    finally:
        engine.dispose()


def is_duplicate(
    company_name: str,
    domain: str,
    contact_email: str,
    table_name: str = "leads",
    db_url: str = None,
) -> bool:
    """
    Convenience wrapper: generate hash and check in one call.

    Returns True if the lead already exists in the database.
    """
    h = generate_duplicate_hash(company_name, domain, contact_email)
    return check_duplicate(h, table_name=table_name, db_url=db_url) is not None
