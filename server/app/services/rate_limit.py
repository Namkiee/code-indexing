"""Rate limiting helpers."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException

try:  # pragma: no cover - optional dependency
    from redis import Redis
    from redis.exceptions import RedisError
except ModuleNotFoundError:  # pragma: no cover - fallback for tests
    from app.utils.redis_client import RedisError

    Redis = Any  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass
class _Bucket:
    minute: int
    count: int


class RateLimiter:
    """Rate limiter supporting shared Redis state with in-memory fallback."""

    def __init__(
        self,
        limit_per_minute: int,
        *,
        time_func: Callable[[], float] | None = None,
        redis_client: Redis | None = None,
    ) -> None:
        self._limit = limit_per_minute
        self._time = time_func or time.time
        self._lock = threading.Lock()
        self._buckets: dict[str, _Bucket] = {}
        self._redis = redis_client
        self._redis_enabled = redis_client is not None
        self._redis_warned = False

    def _disable_redis(self, message: str, *, exc: Exception | None = None) -> None:
        if not self._redis_warned:
            logger.warning("%s; falling back to local rate limiting", message, exc_info=exc)
            self._redis_warned = True
        self._redis_enabled = False

    def _check_redis(self, key: str) -> bool:
        if not self._redis_enabled or self._redis is None:
            return False
        redis_key = f"rate-limit:{key}"
        try:
            count = self._redis.incr(redis_key)
            if count == 1:
                self._redis.expire(redis_key, 60)
            if count > self._limit:
                raise HTTPException(status_code=429, detail="rate limit exceeded")
            return True
        except RedisError as exc:
            self._disable_redis("Redis rate limiter failed", exc=exc)
            return False

    def check(self, key: str) -> None:
        if self._check_redis(key):
            return

        minute = int(self._time() // 60)
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or bucket.minute != minute:
                bucket = _Bucket(minute=minute, count=0)
                self._buckets[key] = bucket
            bucket.count += 1
            if bucket.count > self._limit:
                raise HTTPException(status_code=429, detail="rate limit exceeded")

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()
