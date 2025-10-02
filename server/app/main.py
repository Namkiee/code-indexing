"""FastAPI application entrypoint."""

from __future__ import annotations

import json
import logging
import os
import pathlib

from fastapi import FastAPI

from app.api import api_router
from app.api.context import AppContext
from app.config import settings
from app.index.opensearch_store import OSStore
from app.index.qdrant_store import QdrantStore
from app.search.hybrid_search import HybridSearch
from app.search.providers.embedding import build_embedding_provider
from app.search.providers.reranker import build_reranker_provider
from app.search.reranker import CrossEncoderReranker
from app.services.api_key import APIKeyValidator
from app.services.cache import EmbeddingCache, SearchCache
from app.services.metrics import StatsTracker
from app.services.rate_limit import RateLimiter
from app.utils.logging import RequestIdMiddleware, configure_logging

configure_logging()
logger = logging.getLogger(__name__)

TENANT_FILE = pathlib.Path("/app/server/data/tenants.json")
REQUIRE_API_KEY = os.getenv("REQUIRE_API_KEY", "false").lower() == "true"
SEARCH_RATE_PER_MIN = int(os.getenv("LIMIT_SEARCH_PER_MINUTE", "120"))
EMBED_CACHE_SIZE = int(os.getenv("EMBED_CACHE_SIZE", "10000"))
SEARCH_CACHE_TTL_S = int(os.getenv("SEARCH_CACHE_TTL_S", "30"))


def _load_tenant_keys(path: pathlib.Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - defensive log path
        logger.exception("Failed to read tenant key file: %s", path)
        return {}
    if not isinstance(data, dict):
        logger.warning("Tenant key file %s does not contain a mapping", path)
        return {}
    normalized: dict[str, list[str]] = {}
    for tenant, keys in data.items():
        if isinstance(keys, list):
            normalized[str(tenant)] = [str(key) for key in keys]
    return normalized


def create_app() -> FastAPI:
    embed_provider, embed_key, embed_fallback = build_embedding_provider(
        os.getenv("EMBED_PROVIDER"), settings.embed_model
    )
    if embed_fallback:
        logger.warning(
            "Unknown embedding provider '%s'; falling back to '%s'",
            embed_fallback,
            embed_key,
        )

    reranker_provider, reranker_key, reranker_fallback = build_reranker_provider(
        os.getenv("RERANKER_PROVIDER"), settings.reranker_model
    )
    if reranker_fallback:
        logger.warning(
            "Unknown reranker provider '%s'; falling back to '%s'",
            reranker_fallback,
            reranker_key,
        )

    qdrant = QdrantStore()
    opensearch = OSStore()

    searcher = HybridSearch(qdrant, opensearch, embed_provider)
    reranker = CrossEncoderReranker(provider=reranker_provider)

    context = AppContext(
        qdrant=qdrant,
        opensearch=opensearch,
        searcher=searcher,
        reranker=reranker,
        embedding_cache=EmbeddingCache(embed_provider, EMBED_CACHE_SIZE),
        search_cache=SearchCache(SEARCH_CACHE_TTL_S),
        rate_limiter=RateLimiter(SEARCH_RATE_PER_MIN),
        api_keys=APIKeyValidator(_load_tenant_keys(TENANT_FILE), REQUIRE_API_KEY),
        stats=StatsTracker(),
    )

    app = FastAPI(title="Hybrid Code Indexing (Advanced)")
    app.state.context = context  # type: ignore[attr-defined]

    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router)

    return app


app = create_app()
