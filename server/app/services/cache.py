"""Caching utilities for application services."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Hashable, Iterable

try:  # pragma: no cover - optional dependency
    from redis import Redis
    from redis.exceptions import RedisError
except ModuleNotFoundError:  # pragma: no cover - fallback for tests
    from app.utils.redis_client import RedisError

    Redis = Any  # type: ignore[assignment]

from app.search.providers.embedding import EmbeddingProvider

logger = logging.getLogger(__name__)


class _LRUCache:
    """Thread-safe LRU cache used for embedding reuse."""

    def __init__(self, max_size: int) -> None:
        self._max_size = max_size
        self._lock = threading.Lock()
        self._store: OrderedDict[str, list[float]] = OrderedDict()

    def get(self, key: str) -> list[float] | None:
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
    """Provides cached access to embedding encodings with optional Redis backing."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        max_size: int,
        *,
        redis_client: Redis | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        self._provider = provider
        self._cache = _LRUCache(max_size)
        self._redis = redis_client
        self._ttl = ttl_seconds
        self._redis_enabled = redis_client is not None
        self._redis_warned = False

    def _redis_key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"embeddings:{digest}"

    def _disable_redis(self, message: str, *, exc: Exception | None = None) -> None:
        if not self._redis_warned:
            logger.warning("%s; falling back to local embedding cache", message, exc_info=exc)
            self._redis_warned = True
        self._redis_enabled = False

    def encode(self, text: str) -> list[float]:
        cached = self._cache.get(text)
        if cached is not None:
            return cached

        if self._redis_enabled and self._redis is not None:
            key = self._redis_key(text)
            try:
                payload = self._redis.get(key)
                if payload is not None:
                    vector = json.loads(payload.decode("utf-8"))
                    self._cache.put(text, vector)
                    return vector
            except (RedisError, json.JSONDecodeError) as exc:
                self._disable_redis("Redis embedding cache read failed", exc=exc)

        vector = self._provider.encode([text], normalize_embeddings=True)[0]
        self._cache.put(text, vector)

        if self._redis_enabled and self._redis is not None:
            key = self._redis_key(text)
            try:
                data = json.dumps(vector).encode("utf-8")
                if self._ttl:
                    self._redis.set(key, data, ex=self._ttl)
                else:
                    self._redis.set(key, data)
            except RedisError as exc:
                self._disable_redis("Redis embedding cache write failed", exc=exc)

        return vector


@dataclass(frozen=True)
class SearchCacheEntry:
    hits: list[dict[str, Any]]
    debug: list[dict[str, Any]]
    bucket: str
    search_id: str
    timestamp: float


class SearchCache:
    """Cache for search responses with TTL semantics and optional Redis."""

    def __init__(
        self,
        ttl_seconds: int,
        *,
        time_func: Callable[[], float] | None = None,
        redis_client: Redis | None = None,
    ) -> None:
        self._ttl = ttl_seconds
        self._time = time_func or time.time
        self._lock = threading.Lock()
        self._store: dict[Hashable, SearchCacheEntry] = {}
        self._redis = redis_client
        self._redis_enabled = redis_client is not None
        self._redis_warned = False

    def _redis_key(self, key: Hashable) -> str:
        try:
            serialised = json.dumps(key, sort_keys=True, default=str)
        except TypeError:
            serialised = repr(key)
        digest = hashlib.sha256(serialised.encode("utf-8")).hexdigest()
        return f"search-cache:{digest}"

    def _disable_redis(self, message: str, *, exc: Exception | None = None) -> None:
        if not self._redis_warned:
            logger.warning("%s; falling back to local search cache", message, exc_info=exc)
            self._redis_warned = True
        self._redis_enabled = False

    def _from_redis(self, key: Hashable) -> SearchCacheEntry | None:
        if not self._redis_enabled or self._redis is None:
            return None
        try:
            payload = self._redis.get(self._redis_key(key))
        except RedisError as exc:
            self._disable_redis("Redis search cache read failed", exc=exc)
            return None
        if payload is None:
            return None
        try:
            data = json.loads(payload.decode("utf-8"))
            return SearchCacheEntry(
                hits=data["hits"],
                debug=data.get("debug", []),
                bucket=data["bucket"],
                search_id=data["search_id"],
                timestamp=data["timestamp"],
            )
        except (KeyError, json.JSONDecodeError) as exc:
            logger.debug("Invalid entry in Redis search cache", exc_info=exc)
            return None

    def _store_redis(self, key: Hashable, entry: SearchCacheEntry) -> None:
        if not self._redis_enabled or self._redis is None:
            return
        payload = json.dumps(
            {
                "hits": entry.hits,
                "debug": entry.debug,
                "bucket": entry.bucket,
                "search_id": entry.search_id,
                "timestamp": entry.timestamp,
            }
        ).encode("utf-8")
        try:
            self._redis.set(self._redis_key(key), payload, ex=self._ttl)
        except RedisError as exc:
            self._disable_redis("Redis search cache write failed", exc=exc)

    def get(self, key: Hashable) -> SearchCacheEntry | None:
        entry = self._from_redis(key)
        if entry is not None:
            return entry

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
        self._store_redis(key, entry)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
