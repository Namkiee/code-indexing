"""Search-related endpoints."""

from __future__ import annotations

import os
import time
import uuid
import logging

from fastapi import APIRouter, Depends, Header, Request

from app.api.context import AppContext
from app.api.deps import provide_context
from app.config import settings
from app.models.schemas import (
    FetchLinesRequest,
    FetchLinesResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from app.utils.jsonl import append_jsonl

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


@router.post("/search", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    request: Request,
    *,
    x_api_key: str | None = Header(default=None),
    context: AppContext = Depends(provide_context),
) -> SearchResponse:
    context.api_keys.enforce(req.tenant_id, x_api_key)

    client_key = x_api_key or (request.client.host if request.client else "anonymous")
    context.rate_limiter.check(client_key)

    start = time.time()

    logger.info(
        "search_started",
        extra={
            "tenant_id": req.tenant_id,
            "repo_id": req.repo_id,
            "query": req.query,
            "lang": req.lang,
            "top_k": req.top_k,
        },
    )

    cache_key = (
        req.tenant_id,
        req.repo_id,
        req.query,
        req.lang,
        req.dir_hint,
        req.exclude_tests,
        req.top_k,
    )
    cached_entry = context.search_cache.get(cache_key)

    if cached_entry:
        hits = cached_entry.hits
        debug = cached_entry.debug
        bucket = cached_entry.bucket
        search_id = cached_entry.search_id
        cache_hit = True
    else:
        search_id = uuid.uuid4().hex[:16]
        bucket = "control" if int(search_id[-1], 16) % 2 == 0 else "variant"

        original_alpha, original_beta = context.searcher.alpha, context.searcher.beta
        if bucket == "variant":
            context.searcher.alpha = float(os.getenv("AB_VARIANT_ALPHA", context.searcher.alpha))
            context.searcher.beta = float(os.getenv("AB_VARIANT_BETA", context.searcher.beta))

        hits, debug = context.searcher.search_with_debug(
            tenant_id=req.tenant_id,
            repo_id=req.repo_id,
            query=req.query,
            top_k=req.top_k,
            filters={
                "lang": req.lang,
                "dir_hint": req.dir_hint,
                "exclude_tests": req.exclude_tests,
            },
        )
        context.searcher.alpha, context.searcher.beta = original_alpha, original_beta

        context.search_cache.set(
            cache_key,
            hits=hits,
            debug=debug,
            bucket=bucket,
            search_id=search_id,
        )
        cache_hit = False

    need_fetch = req.repo_id in settings.privacy_repo_ids

    append_jsonl(
        "/app/server/data/search_log.jsonl",
        {
            "search_id": search_id,
            "tenant_id": req.tenant_id,
            "repo_id": req.repo_id,
            "query": req.query,
            "timestamp": time.time(),
            "candidates": debug,
            "bucket": bucket,
        },
    )

    duration_ms = int((time.time() - start) * 1000)

    logger.info(
        "search_completed",
        extra={
            "tenant_id": req.tenant_id,
            "repo_id": req.repo_id,
            "query": req.query,
            "top_k": req.top_k,
            "cache_hit": cache_hit,
            "variant": bucket,
            "duration_ms": duration_ms,
            "result_count": len(hits),
            "search_id": search_id,
        },
    )

    if debug:
        logger.debug(
            "search_candidates",
            extra={
                "tenant_id": req.tenant_id,
                "repo_id": req.repo_id,
                "query": req.query,
                "variant": bucket,
                "cache_hit": cache_hit,
                "search_id": search_id,
                "candidates": debug,
            },
        )

    context.stats.record_search(duration_ms)

    return SearchResponse(
        search_id=search_id,
        bucket=bucket,
        need_fetch_lines=need_fetch,
        hits=[SearchHit(**hit) for hit in hits],
    )


@router.post("/search/fetch-lines", response_model=FetchLinesResponse)
async def fetch_lines(
    req: FetchLinesRequest,
    *,
    x_api_key: str | None = Header(default=None),
    context: AppContext = Depends(provide_context),
) -> FetchLinesResponse:
    context.api_keys.enforce(req.tenant_id, x_api_key)

    passages = [item.raw_lines for item in req.items]
    scores = context.reranker.rerank(req.query, passages)
    ranked = sorted(zip(req.items, scores), key=lambda pair: pair[1], reverse=True)[: req.top_k]

    hits = [
        SearchHit(
            chunk_id=item.chunk_id,
            score=float(score),
            path_tokens=[],
            line_span=[0, 0],
            repo_id=req.repo_id,
            preview=None,
        )
        for item, score in ranked
    ]

    return FetchLinesResponse(hits=hits)
