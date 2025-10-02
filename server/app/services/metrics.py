"""Application metrics tracking."""

from __future__ import annotations

import threading
from typing import Any, Dict


class StatsTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stats: Dict[str, Any] = {
            "search_total": 0,
            "search_err": 0,
            "feedback_total": 0,
            "index_total": 0,
            "avg_search_ms": 0.0,
        }

    def record_search(self, duration_ms: float) -> None:
        with self._lock:
            self._stats["search_total"] += 1
            # exponential moving average similar to previous behaviour
            self._stats["avg_search_ms"] = (
                self._stats["avg_search_ms"] * 0.99 + duration_ms * 0.01
            )

    def increment_index(self, amount: int) -> None:
        if amount <= 0:
            return
        with self._lock:
            self._stats["index_total"] += amount

    def increment_feedback(self) -> None:
        with self._lock:
            self._stats["feedback_total"] += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)
