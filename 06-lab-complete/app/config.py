"""Configuration helpers for Lab 06 production app."""

import os
from dataclasses import dataclass


def _read_int_env(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(value, minimum)


def _read_float_env(name: str, default: float, minimum: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        value = default
    return max(value, minimum)


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("ENVIRONMENT", "development").strip().lower()
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()
    agent_api_key: str = os.getenv("AGENT_API_KEY", "").strip()
    rate_limit_per_minute: int = _read_int_env("RATE_LIMIT_PER_MINUTE", 10, 1)
    monthly_budget_usd: float = _read_float_env("MONTHLY_BUDGET_USD", 10.0, 0.01)


settings = Settings()
"""Production config — 12-Factor: all values come from environment variables."""
import logging
import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    # Server
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # App
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Production AI Agent"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))

    # LLM
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))

    # Security
    agent_api_key: str = field(
        default_factory=lambda: os.getenv("AGENT_API_KEY", "dev-key-change-me-in-production")
    )
    allowed_origins: list = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
            if origin.strip()
        ]
    )

    # Rate limiting & budget (submission checklist requirements)
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    )
    monthly_budget_usd: float = field(
        default_factory=lambda: float(os.getenv("MONTHLY_BUDGET_USD", "10.0"))
    )

    # Storage
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    def validate(self):
        logger = logging.getLogger(__name__)
        if self.environment == "production":
            if self.agent_api_key == "dev-key-change-me-in-production":
                raise ValueError("AGENT_API_KEY must be set in production.")
            if not self.redis_url:
                raise ValueError("REDIS_URL must be set in production.")

        if self.rate_limit_per_minute <= 0:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be > 0.")
        if self.monthly_budget_usd <= 0:
            raise ValueError("MONTHLY_BUDGET_USD must be > 0.")

        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not set — using mock LLM")
        return self


settings = Settings().validate()
