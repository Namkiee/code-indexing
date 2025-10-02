from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.cache import EmbeddingCache, SearchCache
from app.services.rate_limit import RateLimiter


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
