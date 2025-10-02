"""Rate limiting helpers."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from fastapi import HTTPException


@dataclass
class _Bucket:
    minute: int
    count: int


class RateLimiter:
    """Simple in-memory rate limiter with per-minute buckets."""

    def __init__(
        self,
        limit_per_minute: int,
        *,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        self._limit = limit_per_minute
        self._time = time_func or time.time
        self._lock = threading.Lock()
        self._buckets: dict[str, _Bucket] = {}

    def check(self, key: str) -> None:
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
