"""
MCRcore Growth Engine - Base Agent

All Growth Engine agents inherit from BaseAgent. Provides:
    - Structured logging per agent
    - Configuration loading
    - Audit trail support
    - Standard run() interface
"""

import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from src.utils.logger import get_agent_logger

load_dotenv()


class BaseAgent(ABC):
    """
    Abstract base class for all MCRcore Growth Engine agents.

    Subclasses must implement the run() method. All actions are
    automatically logged to the audit trail.

    Attributes:
        name: Human-readable agent name.
        description: What this agent does.
        agent_id: Unique ID for this agent instance.
        audit_trail: In-memory list of all logged actions.
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.agent_id = str(uuid.uuid4())
        self.created_at = datetime.now(timezone.utc)
        self.logger = get_agent_logger(name)
        self.audit_trail: List[Dict[str, Any]] = []
        self._config: Dict[str, Any] = {}

        self.logger.info(
            f"Agent initialized: {self.name} ({self.agent_id[:8]})",
            extra={"agent": self.name, "action": "init"},
        )

    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """
        Execute the agent's primary task.

        Must be implemented by all subclasses. Should return a result
        dict or value appropriate to the agent's function.
        """
        pass

    def log_action(
        self,
        action: str,
        detail: str = "",
        status: str = "success",
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Log an action to both the logger and the in-memory audit trail.

        Args:
            action: Short action identifier (e.g. 'scrape', 'email_sent').
            detail: Human-readable description.
            status: Action status ('success', 'failure', 'skipped', 'pending').
            metadata: Additional key-value data.

        Returns:
            The audit trail entry dict.
        """
        entry = {
            "audit_id": str(uuid.uuid4()),
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "action": action,
            "detail": detail,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        self.audit_trail.append(entry)

        log_level = "info" if status == "success" else "warning"
        log_fn = getattr(self.logger, log_level)
        log_fn(
            f"[{action}] {detail} (status={status})",
            extra={
                "agent": self.name,
                "action": action,
                "detail": detail,
                "audit_id": entry["audit_id"],
            },
        )

        return entry

    def get_config(self, key: str = None, default: Any = None) -> Any:
        """
        Get agent configuration values.

        Configuration is loaded from environment variables prefixed with
        the agent name (uppercased, hyphens replaced with underscores),
        and can be supplemented with set_config().

        Args:
            key: Specific config key. If None, returns all config.
            default: Default value if key not found.

        Returns:
            Config value or full config dict.
        """
        if key is None:
            return dict(self._config)

        # Check in-memory config first
        if key in self._config:
            return self._config[key]

        # Fall back to environment variable
        env_prefix = self.name.upper().replace("-", "_").replace(" ", "_")
        env_key = f"{env_prefix}_{key.upper()}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value

        return default

    def set_config(self, key: str, value: Any):
        """Set a config value for this agent."""
        self._config[key] = value
        self.logger.debug(f"Config set: {key}={value}", extra={"agent": self.name})

    def get_audit_trail(
        self,
        action_filter: str = None,
        status_filter: str = None,
        limit: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit trail entries with optional filtering.

        Args:
            action_filter: Only return entries with this action.
            status_filter: Only return entries with this status.
            limit: Maximum number of entries to return (most recent first).

        Returns:
            List of audit trail entry dicts.
        """
        entries = self.audit_trail

        if action_filter:
            entries = [e for e in entries if e["action"] == action_filter]
        if status_filter:
            entries = [e for e in entries if e["status"] == status_filter]

        # Most recent first
        entries = list(reversed(entries))

        if limit:
            entries = entries[:limit]

        return entries

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for this agent's audit trail."""
        total = len(self.audit_trail)
        successes = sum(1 for e in self.audit_trail if e["status"] == "success")
        failures = sum(1 for e in self.audit_trail if e["status"] == "failure")
        skipped = sum(1 for e in self.audit_trail if e["status"] == "skipped")

        return {
            "agent_name": self.name,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat(),
            "total_actions": total,
            "successes": successes,
            "failures": failures,
            "skipped": skipped,
            "success_rate": (successes / total * 100) if total > 0 else 0.0,
        }

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name='{self.name}' "
            f"id='{self.agent_id[:8]}' actions={len(self.audit_trail)}>"
        )
