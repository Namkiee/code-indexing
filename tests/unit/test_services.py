from __future__ import annotations

import pytest
from fastapi import HTTPException

try:  # pragma: no cover - allows running tests without redis installed
    from redis.exceptions import RedisError
except ModuleNotFoundError:  # pragma: no cover - fallback for CI environments
    from app.utils.redis_client import RedisError

from app.services.cache import EmbeddingCache, SearchCache
from app.services.rate_limit import RateLimiter


class DummyRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.expiry: dict[str, int] = {}

    def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    def set(self, key: str, value: bytes, ex: int | None = None) -> None:
        self.store[key] = value
        if ex is not None:
            self.expiry[key] = ex

    def incr(self, key: str) -> int:
        current = int(self.store.get(key, b"0").decode("utf-8")) if key in self.store else 0
        current += 1
        self.store[key] = str(current).encode("utf-8")
        return current

    def expire(self, key: str, ttl: int) -> None:
        self.expiry[key] = ttl


class DummyProvider:
    def __init__(self) -> None:
        self.calls = 0

    def encode(self, texts, normalize_embeddings=True):  # type: ignore[override]
        self.calls += 1
        return [[float(len(texts))] for _ in texts]


def test_embedding_cache_reuses_vectors():
    provider = DummyProvider()
    cache = EmbeddingCache(provider, max_size=10)

    first = cache.encode("hello")
    second = cache.encode("hello")

    assert first == second
    assert provider.calls == 1


def test_search_cache_honours_ttl():
    now = [0.0]

    def fake_time() -> float:
        return now[0]

    cache = SearchCache(ttl_seconds=10, time_func=fake_time)
    cache.set("key", hits=[{"chunk_id": 1}], bucket="control", search_id="abc")
    assert cache.get("key") is not None
    now[0] = 11
    assert cache.get("key") is None


def test_rate_limiter_blocks_after_limit():
    now = [0.0]

    def fake_time() -> float:
        return now[0]

    limiter = RateLimiter(limit_per_minute=2, time_func=fake_time)
    limiter.check("tenant")
    limiter.check("tenant")
    with pytest.raises(HTTPException):
        limiter.check("tenant")
    now[0] = 61
    limiter.check("tenant")  # new window succeeds


def test_embedding_cache_uses_redis_across_instances():
    provider_a = DummyProvider()
    redis = DummyRedis()
    cache_a = EmbeddingCache(provider_a, max_size=1, redis_client=redis, ttl_seconds=30)

    result = cache_a.encode("redis-shared")
    assert provider_a.calls == 1

    provider_b = DummyProvider()
    cache_b = EmbeddingCache(provider_b, max_size=1, redis_client=redis, ttl_seconds=30)
    cached = cache_b.encode("redis-shared")

    assert cached == result
    assert provider_b.calls == 0


def test_search_cache_reads_from_redis():
    redis = DummyRedis()
    cache_a = SearchCache(30, redis_client=redis)
    cache_key = ("tenant", "repo", "query", None, None, False, 5)
    cache_a.set(
        cache_key,
        hits=[{"chunk_id": 1}],
        debug=[{"score": 0.1}],
        bucket="control",
        search_id="abc123",
    )

    cache_b = SearchCache(30, redis_client=redis)
    entry = cache_b.get(cache_key)

    assert entry is not None
    assert entry.bucket == "control"
    assert entry.hits[0]["chunk_id"] == 1


def test_rate_limiter_uses_redis():
    redis = DummyRedis()
    limiter = RateLimiter(limit_per_minute=2, redis_client=redis)
    limiter.check("key")
    limiter.check("key")
    with pytest.raises(HTTPException):
        limiter.check("key")
    assert redis.expiry["rate-limit:key"] == 60


def test_rate_limiter_falls_back_when_redis_fails():
    class FailingRedis(DummyRedis):
        def incr(self, key: str) -> int:  # type: ignore[override]
            raise RedisError("boom")

    redis = FailingRedis()
    now = [0.0]

    def fake_time() -> float:
        return now[0]

    limiter = RateLimiter(limit_per_minute=1, time_func=fake_time, redis_client=redis)
    limiter.check("key")
    with pytest.raises(HTTPException):
        limiter.check("key")
