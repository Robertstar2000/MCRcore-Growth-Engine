"""
MCRcore Growth Engine - Structured Logging

Provides file and console logging with structured output.
Logs are written to the logs/ directory.
"""

import logging
import logging.handlers
import os
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", "logs")


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter for machine-readable logs."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Attach any extra fields passed via the `extra` kwarg
        for key in ("agent", "action", "detail", "audit_id"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        return json.dumps(log_entry)


class ConsoleFormatter(logging.Formatter):
    """Human-readable colored console formatter."""

    COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[1;31m",  # bold red
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = ""
        if hasattr(record, "agent"):
            prefix = f"[{record.agent}] "
        return (
            f"{color}{ts} {record.levelname:<8}{self.RESET} "
            f"{prefix}{record.getMessage()}"
        )


def setup_logger(name: str = "mcr_growth_engine", level: str = None) -> logging.Logger:
    """
    Create and configure a logger with both file and console handlers.

    Args:
        name: Logger name (usually module or agent name).
        level: Override log level. Defaults to LOG_LEVEL env var.

    Returns:
        Configured logging.Logger instance.
    """
    level = level or LOG_LEVEL
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level, logging.INFO))

    # --- Ensure log directory exists ---
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    # --- File handler (structured JSON, rotating) ---
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "mcr_growth_engine.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(StructuredFormatter())

    # --- Console handler (human-readable) ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level, logging.INFO))
    console_handler.setFormatter(ConsoleFormatter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_agent_logger(agent_name: str) -> logging.Logger:
    """Get a child logger scoped to a specific agent."""
    return setup_logger(f"mcr_growth_engine.{agent_name}")


# Module-level default logger
logger = setup_logger()
