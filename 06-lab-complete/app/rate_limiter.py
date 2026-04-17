"""Sliding-window rate limiter with optional Redis backend."""

import time
import uuid
from collections import defaultdict, deque
from threading import Lock


class RateLimitExceeded(Exception):
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        super().__init__("Rate limit exceeded")


class RateLimiter:
    def __init__(self, limit_per_minute: int = 10, window_seconds: int = 60):
        self.limit_per_minute = limit_per_minute
        self.window_seconds = window_seconds
        self._redis = None
        self._memory_windows: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def set_redis_client(self, redis_client) -> None:
        self._redis = redis_client

    def check(self, identity: str) -> dict:
        now = time.time()

        if self._redis is not None:
            key = f"rl:{identity}"
            token = f"{int(now * 1000)}-{uuid.uuid4().hex}"
            window_start = now - self.window_seconds
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {token: now})
            pipe.zcard(key)
            pipe.expire(key, self.window_seconds + 5)
            _, _, request_count, _ = pipe.execute()
        else:
            with self._lock:
                window = self._memory_windows[identity]
                while window and window[0] < now - self.window_seconds:
                    window.popleft()
                window.append(now)
                request_count = len(window)

        if request_count > self.limit_per_minute:
            raise RateLimitExceeded(self.limit_per_minute, self.window_seconds)

        return {
            "limit": self.limit_per_minute,
            "remaining": max(self.limit_per_minute - request_count, 0),
        }
"""Redis-backed sliding-window rate limiter."""
import time
import uuid
from collections import defaultdict, deque

from fastapi import HTTPException


class RateLimiter:
    def __init__(self, limit_per_minute: int = 10, window_seconds: int = 60):
        self.limit_per_minute = limit_per_minute
        self.window_seconds = window_seconds
        self._redis = None
        self._memory_windows: dict[str, deque] = defaultdict(deque)

    def set_redis_client(self, redis_client):
        self._redis = redis_client

    def check(self, identity: str) -> dict:
        """Raise HTTP 429 when request rate exceeds configured threshold."""
        now = time.time()

        if self._redis is not None:
            key = f"rl:{identity}"
            token = f"{int(now * 1000)}-{uuid.uuid4().hex}"
            window_start = now - self.window_seconds

            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {token: now})
            pipe.zcard(key)
            pipe.expire(key, self.window_seconds + 5)
            _, _, request_count, _ = pipe.execute()
        else:
            window = self._memory_windows[identity]
            while window and window[0] < now - self.window_seconds:
                window.popleft()
            window.append(now)
            request_count = len(window)

        if request_count > self.limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": self.limit_per_minute,
                    "window_seconds": self.window_seconds,
                },
                headers={"Retry-After": str(self.window_seconds)},
            )

        return {
            "limit": self.limit_per_minute,
            "remaining": max(self.limit_per_minute - request_count, 0),
        }
