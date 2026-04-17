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
