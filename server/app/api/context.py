"""Application context shared across routers."""

from __future__ import annotations

from dataclasses import dataclass

from app.index.opensearch_store import OSStore
from app.index.qdrant_store import QdrantStore
from app.search.hybrid_search import HybridSearch
from app.search.reranker import CrossEncoderReranker
from app.services.api_key import APIKeyValidator
from app.services.cache import EmbeddingCache, SearchCache
from app.services.metrics import StatsTracker
from app.services.rate_limit import RateLimiter


@dataclass
class AppContext:
    qdrant: QdrantStore
    opensearch: OSStore
    searcher: HybridSearch
    reranker: CrossEncoderReranker
    embedding_cache: EmbeddingCache
    search_cache: SearchCache
    rate_limiter: RateLimiter
    api_keys: APIKeyValidator
    stats: StatsTracker
