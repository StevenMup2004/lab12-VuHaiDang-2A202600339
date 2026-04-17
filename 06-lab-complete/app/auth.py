"""Authentication helpers for API key protected endpoints."""

import hashlib
import hmac
import os


def verify_api_key(provided_key: str, expected_key: str | None = None) -> bool:
    """Return True when API key matches expected secret.

    If expected key is empty, auth is treated as disabled.
    """
    expected = (expected_key if expected_key is not None else os.getenv("AGENT_API_KEY", "")).strip()
    provided = (provided_key or "").strip()
    if not expected:
        return True
    return hmac.compare_digest(provided, expected)


def api_key_bucket(api_key: str) -> str:
    """Return a short hash bucket for privacy-safe rate-limit identity."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
"""Authentication helpers for API key protected endpoints."""
import hashlib

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Validate API key provided in X-API-Key header."""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include header: X-API-Key: <your-key>",
        )
    if api_key != settings.agent_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    return api_key


def api_key_bucket(api_key: str) -> str:
    """Return a stable anonymized identifier for rate-limit/budget keys."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
