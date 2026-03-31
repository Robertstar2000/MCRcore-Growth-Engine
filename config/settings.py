"""
MCRcore Growth Engine - Main Settings
Loads all configuration from environment variables with sensible defaults.
All secrets use os.getenv() with PLACEHOLDER markers for required values.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DatabaseConfig:
    """Database connection settings."""
    # PLACEHOLDER: Set DATABASE_URL to your PostgreSQL connection string
    url: str = os.getenv("DATABASE_URL", "postgresql://localhost:5432/mcr_growth_engine")
    pool_size: int = int(os.getenv("DB_POOL_SIZE", "10"))
    max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    echo_sql: bool = os.getenv("DB_ECHO_SQL", "false").lower() == "true"


@dataclass
class APIKeys:
    """Third-party API keys. All PLACEHOLDER - must be set via env vars."""
    # PLACEHOLDER: LinkedIn Sales Navigator API credentials
    linkedin_sales_nav_key: str = os.getenv("LINKEDIN_SALES_NAV_KEY", "PLACEHOLDER")
    linkedin_sales_nav_secret: str = os.getenv("LINKEDIN_SALES_NAV_SECRET", "PLACEHOLDER")

    # PLACEHOLDER: Apollo.io API key
    apollo_api_key: str = os.getenv("APOLLO_API_KEY", "PLACEHOLDER")

    # PLACEHOLDER: ZoomInfo API credentials
    zoominfo_api_key: str = os.getenv("ZOOMINFO_API_KEY", "PLACEHOLDER")
    zoominfo_client_id: str = os.getenv("ZOOMINFO_CLIENT_ID", "PLACEHOLDER")

    # PLACEHOLDER: Email verification service (e.g., ZeroBounce, NeverBounce)
    email_verify_api_key: str = os.getenv("EMAIL_VERIFY_API_KEY", "PLACEHOLDER")

    # PLACEHOLDER: CRM integration (e.g., HubSpot, Salesforce)
    crm_api_key: str = os.getenv("CRM_API_KEY", "PLACEHOLDER")

    def has_valid_key(self, service: str) -> bool:
        """Check if a given service key is set (not PLACEHOLDER)."""
        key = getattr(self, f"{service}", None)
        return key is not None and key != "PLACEHOLDER"


@dataclass
class TeamsConfig:
    """Microsoft Teams webhook configuration for notifications."""
    # PLACEHOLDER: Set TEAMS_WEBHOOK_URL to your Teams incoming webhook URL
    webhook_url: str = os.getenv("TEAMS_WEBHOOK_URL", "PLACEHOLDER")
    # Channel-specific webhooks for routing different alert types
    webhook_deals: str = os.getenv("TEAMS_WEBHOOK_DEALS", "PLACEHOLDER")
    webhook_alerts: str = os.getenv("TEAMS_WEBHOOK_ALERTS", "PLACEHOLDER")
    webhook_daily_digest: str = os.getenv("TEAMS_WEBHOOK_DIGEST", "PLACEHOLDER")
    enabled: bool = os.getenv("TEAMS_NOTIFICATIONS_ENABLED", "true").lower() == "true"


@dataclass
class EmailConfig:
    """SMTP email configuration for outbound sequences."""
    # PLACEHOLDER: Set these to your SMTP server details
    smtp_host: str = os.getenv("SMTP_HOST", "PLACEHOLDER")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "PLACEHOLDER")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "PLACEHOLDER")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # Sender identity
    from_name: str = os.getenv("EMAIL_FROM_NAME", "MCRcore")
    from_address: str = os.getenv("EMAIL_FROM_ADDRESS", "PLACEHOLDER")
    reply_to: str = os.getenv("EMAIL_REPLY_TO", "PLACEHOLDER")

    # Rate limiting
    max_sends_per_hour: int = int(os.getenv("EMAIL_MAX_PER_HOUR", "50"))
    max_sends_per_day: int = int(os.getenv("EMAIL_MAX_PER_DAY", "200"))

    # Warm-up mode: gradually increase send volume
    warmup_enabled: bool = os.getenv("EMAIL_WARMUP_ENABLED", "true").lower() == "true"
    warmup_daily_increment: int = int(os.getenv("EMAIL_WARMUP_INCREMENT", "5"))


@dataclass
class LLMConfig:
    """LLM / AI model configuration for content generation and scoring."""
    # PLACEHOLDER: Set your OpenAI or compatible API key
    api_key: str = os.getenv("LLM_API_KEY", "PLACEHOLDER")
    api_base_url: str = os.getenv("LLM_API_BASE_URL", "https://api.openai.com/v1")

    # Model selection
    primary_model: str = os.getenv("LLM_PRIMARY_MODEL", "gpt-4o")
    fast_model: str = os.getenv("LLM_FAST_MODEL", "gpt-4o-mini")
    embedding_model: str = os.getenv("LLM_EMBEDDING_MODEL", "text-embedding-3-small")

    # Generation parameters
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))

    # Rate limiting
    max_requests_per_minute: int = int(os.getenv("LLM_RPM", "60"))
    max_tokens_per_minute: int = int(os.getenv("LLM_TPM", "150000"))

    # Cost controls
    daily_budget_usd: float = float(os.getenv("LLM_DAILY_BUDGET_USD", "10.00"))
    alert_threshold_pct: float = float(os.getenv("LLM_ALERT_THRESHOLD_PCT", "0.8"))


@dataclass
class AppConfig:
    """Top-level application settings."""
    app_name: str = "MCRcore Growth Engine"
    environment: str = os.getenv("APP_ENV", "development")
    debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Sub-configs
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api_keys: APIKeys = field(default_factory=APIKeys)
    teams: TeamsConfig = field(default_factory=TeamsConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    # Agent orchestration
    agent_concurrency: int = int(os.getenv("AGENT_CONCURRENCY", "4"))
    pipeline_tick_seconds: int = int(os.getenv("PIPELINE_TICK_SECONDS", "300"))

    def is_production(self) -> bool:
        return self.environment == "production"

    def validate(self) -> list[str]:
        """Return list of config warnings (missing keys, placeholders, etc.)."""
        warnings = []
        if self.database.url == "postgresql://localhost:5432/mcr_growth_engine":
            warnings.append("DATABASE_URL is using default local value")
        if self.api_keys.apollo_api_key == "PLACEHOLDER":
            warnings.append("APOLLO_API_KEY not set")
        if self.llm.api_key == "PLACEHOLDER":
            warnings.append("LLM_API_KEY not set")
        if self.email.smtp_host == "PLACEHOLDER":
            warnings.append("SMTP_HOST not set")
        if self.teams.webhook_url == "PLACEHOLDER":
            warnings.append("TEAMS_WEBHOOK_URL not set")
        return warnings


# Singleton instance - import this from other modules
settings = AppConfig()
