"""Monthly cost guard with Redis-backed usage tracking."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException


INPUT_COST_PER_1K = 0.00015
OUTPUT_COST_PER_1K = 0.0006


class CostGuard:
    def __init__(self, monthly_budget_usd: float = 10.0):
        self.monthly_budget_usd = monthly_budget_usd
        self._redis = None
        self._memory_usage: dict[str, float] = defaultdict(float)

    def set_redis_client(self, redis_client):
        self._redis = redis_client

    @staticmethod
    def estimate_cost(input_tokens: int, output_tokens: int) -> float:
        input_cost = (input_tokens / 1000) * INPUT_COST_PER_1K
        output_cost = (output_tokens / 1000) * OUTPUT_COST_PER_1K
        return round(input_cost + output_cost, 6)

    @staticmethod
    def _month_prefix() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    @staticmethod
    def _seconds_until_next_month() -> int:
        now = datetime.now(timezone.utc)
        next_month = (now.replace(day=28, hour=0, minute=0, second=0, microsecond=0) + timedelta(days=4)).replace(day=1)
        return int((next_month - now).total_seconds()) + 86400

    def _usage_key(self, user_id: str) -> str:
        return f"budget:{self._month_prefix()}:{user_id}"

    def get_usage(self, user_id: str) -> float:
        key = self._usage_key(user_id)
        if self._redis is not None:
            val = self._redis.get(key)
            return round(float(val) if val else 0.0, 6)
        return round(self._memory_usage[key], 6)

    def check_budget(self, user_id: str, estimated_cost: float):
        used = self.get_usage(user_id)
        if used + estimated_cost > self.monthly_budget_usd:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Monthly budget exceeded",
                    "used_usd": used,
                    "budget_usd": self.monthly_budget_usd,
                    "month": self._month_prefix(),
                },
            )

    def record_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> float:
        cost = self.estimate_cost(input_tokens, output_tokens)
        key = self._usage_key(user_id)

        if self._redis is not None:
            total = self._redis.incrbyfloat(key, cost)
            self._redis.expire(key, self._seconds_until_next_month())
            return round(float(total), 6)

        self._memory_usage[key] += cost
        return round(self._memory_usage[key], 6)
