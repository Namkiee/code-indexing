"""Caching utilities for application services."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Hashable, Iterable, Optional

from app.search.providers.embedding import EmbeddingProvider


class _LRUCache:
    """Thread-safe LRU cache used for embedding reuse."""

    def __init__(self, max_size: int) -> None:
        self._max_size = max_size
        self._lock = threading.Lock()
        self._store: OrderedDict[str, list[float]] = OrderedDict()

    def get(self, key: str) -> Optional[list[float]]:
        with self._lock:
            if key not in self._store:
                return None
            value = self._store.pop(key)
            self._store[key] = value
            return value

    def put(self, key: str, value: list[float]) -> None:
        with self._lock:
            if key in self._store:
                self._store.pop(key)
            self._store[key] = value
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)


class EmbeddingCache:
    """Provides cached access to embedding encodings."""

    def __init__(self, provider: EmbeddingProvider, max_size: int) -> None:
        self._provider = provider
        self._cache = _LRUCache(max_size)

    def encode(self, text: str) -> list[float]:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        vector = self._provider.encode([text], normalize_embeddings=True)[0]
        self._cache.put(text, vector)
        return vector


@dataclass(frozen=True)
class SearchCacheEntry:
    hits: list[dict[str, Any]]
    debug: list[dict[str, Any]]
    bucket: str
    search_id: str
    timestamp: float


class SearchCache:
    """Cache for search responses with TTL semantics."""

    def __init__(self, ttl_seconds: int, time_func: Callable[[], float] | None = None) -> None:
        self._ttl = ttl_seconds
        self._time = time_func or time.time
        self._lock = threading.Lock()
        self._store: dict[Hashable, SearchCacheEntry] = {}

    def get(self, key: Hashable) -> Optional[SearchCacheEntry]:
        now = self._time()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if now - entry.timestamp > self._ttl:
                self._store.pop(key, None)
                return None
            return entry

    def set(
        self,
        key: Hashable,
        *,
        hits: Iterable[dict[str, Any]],
        debug: Iterable[dict[str, Any]] | None = None,
        bucket: str,
        search_id: str,
    ) -> None:
        entry = SearchCacheEntry(
            hits=list(hits),
            debug=list(debug or []),
            bucket=bucket,
            search_id=search_id,
            timestamp=self._time(),
        )
        with self._lock:
            self._store[key] = entry

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
