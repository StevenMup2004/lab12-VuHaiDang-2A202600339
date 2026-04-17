"""Production AI Agent — Day 12 final submission."""
import json
import logging
import signal
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.auth import api_key_bucket, verify_api_key
from app.config import settings
from app.cost_guard import CostGuard
from app.rate_limiter import RateLimiter
from utils.mock_llm import ask as llm_ask


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)


START_TIME = time.time()
_is_ready = False
_is_shutting_down = False
_total_requests = 0
_error_count = 0

_redis_client = None
_rate_limiter = RateLimiter(limit_per_minute=settings.rate_limit_per_minute)
_cost_guard = CostGuard(monthly_budget_usd=settings.monthly_budget_usd)


def _connect_redis():
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception as exc:
        logger.warning(
            json.dumps(
                {
                    "event": "redis_connection_failed",
                    "error": str(exc),
                }
            )
        )
        return None


def _redis_ok() -> bool:
    if _redis_client is None:
        return False
    try:
        _redis_client.ping()
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready, _is_shutting_down, _redis_client

    _is_shutting_down = False
    _redis_client = _connect_redis()
    _rate_limiter.set_redis_client(_redis_client)
    _cost_guard.set_redis_client(_redis_client)

    # In production, Redis is required for stateless rate-limit and monthly budget.
    _is_ready = _redis_ok() if settings.environment == "production" else True

    logger.info(
        json.dumps(
            {
                "event": "startup",
                "app": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment,
                "redis_connected": _redis_ok(),
            }
        )
    )

    yield

    _is_shutting_down = True
    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type", "Authorization"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    global _total_requests, _error_count

    _total_requests += 1
    started_at = time.time()

    try:
        response: Response = await call_next(request)
    except Exception:
        _error_count += 1
        raise

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if "server" in response.headers:
        del response.headers["server"]

    elapsed_ms = round((time.time() - started_at) * 1000, 1)
    logger.info(
        json.dumps(
            {
                "event": "request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": elapsed_ms,
            }
        )
    )
    return response


class AskRequest(BaseModel):
    user_id: str = Field(default="test", min_length=1, max_length=64)
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    usage: dict
    timestamp: str


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.post("/ask", response_model=AskResponse)
async def ask_agent(body: AskRequest, request: Request, api_key: str = Depends(verify_api_key)):
    if _is_shutting_down:
        raise HTTPException(status_code=503, detail="Service is shutting down")

    if settings.environment == "production" and not _redis_ok():
        raise HTTPException(status_code=503, detail="Redis unavailable")

    user_scope = body.user_id.strip()
    key_scope = api_key_bucket(api_key)
    identity = f"{user_scope}:{key_scope}"

    rate_info = _rate_limiter.check(identity)

    input_tokens = len(body.question.split()) * 2
    estimated_output_tokens = max(20, min(200, input_tokens * 2))
    estimated_cost = _cost_guard.estimate_cost(input_tokens, estimated_output_tokens)
    _cost_guard.check_budget(user_scope, estimated_cost)

    answer = llm_ask(body.question)

    output_tokens = len(answer.split()) * 2
    total_monthly_spend = _cost_guard.record_usage(user_scope, input_tokens, output_tokens)

    logger.info(
        json.dumps(
            {
                "event": "ask",
                "user_id": user_scope,
                "client_ip": request.client.host if request.client else "unknown",
                "question_len": len(body.question),
            }
        )
    )

    return AskResponse(
        user_id=user_scope,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        usage={
            "requests_remaining": rate_info["remaining"],
            "monthly_spend_usd": total_monthly_spend,
            "monthly_budget_usd": settings.monthly_budget_usd,
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/health")
def health():
    redis_connected = _redis_ok()
    status = "ok"
    if settings.environment == "production" and not redis_connected:
        status = "degraded"

    return {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "redis_connected": redis_connected,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def ready():
    if _is_shutting_down:
        raise HTTPException(status_code=503, detail="Shutting down")

    if not _is_ready:
        raise HTTPException(status_code=503, detail="Not ready")

    if settings.environment == "production" and not _redis_ok():
        raise HTTPException(status_code=503, detail="Redis not ready")

    return {"ready": True}


@app.get("/metrics")
def metrics(_api_key: str = Depends(verify_api_key)):
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _total_requests,
        "error_count": _error_count,
        "redis_connected": _redis_ok(),
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "monthly_budget_usd": settings.monthly_budget_usd,
    }


def _handle_signal(signum, _frame):
    global _is_shutting_down, _is_ready
    _is_shutting_down = True
    _is_ready = False
    logger.info(json.dumps({"event": "signal", "signum": signum}))


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


if __name__ == "__main__":
    logger.info(
        json.dumps(
            {
                "event": "boot",
                "host": settings.host,
                "port": settings.port,
                "environment": settings.environment,
            }
        )
    )
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
