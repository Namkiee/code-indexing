"""Indexing-related endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from qdrant_client.http.models import PointStruct

from app.api.deps import provide_context
from app.api.context import AppContext
from app.config import settings
from app.models.schemas import UploadRequest
from app.utils.s3_utils import get_object_text

router = APIRouter(prefix="/v1")


@router.post("/index/upload")
async def upload(
    req: UploadRequest,
    *,
    x_api_key: str | None = Header(default=None),
    context: AppContext = Depends(provide_context),
) -> dict[str, Any]:
    tenant = req.chunks[0].tenant_id if req.chunks else "default"
    context.api_keys.enforce(tenant, x_api_key)

    points: list[PointStruct] = []
    os_docs: list[dict[str, Any]] = []

    for chunk in req.chunks:
        payload = {
            "chunk_id": chunk.chunk_id,
            "repo_id": chunk.repo_id,
            "path_tokens": chunk.path_tokens,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
            "lang": chunk.lang,
        }
        if chunk.rel_path is not None:
            payload["rel_path"] = chunk.rel_path

        if chunk.privacy_mode:
            assert chunk.vector is not None, "privacy_mode=True면 vector 필요"
            vector = chunk.vector
        else:
            assert chunk.text is not None, "privacy_mode=False면 text 필요"
            vector = context.embedding_cache.encode(chunk.text)
            if chunk.repo_id not in settings.privacy_repo_ids:
                os_docs.append(
                    {
                        "chunk_id": chunk.chunk_id,
                        "repo_id": chunk.repo_id,
                        "path_tokens": chunk.path_tokens,
                        "rel_path": chunk.rel_path or "",
                        "lang": chunk.lang,
                        "line_start": chunk.line_start,
                        "line_end": chunk.line_end,
                        "text": chunk.text,
                    }
                )

        points.append(
            PointStruct(
                id=chunk.chunk_id,
                vector=vector,
                payload=payload,
            )
        )

    if points:
        context.qdrant.upsert_tenant(tenant, points)
    if os_docs:
        context.opensearch.bulk_upsert_tenant(tenant, os_docs)

    context.stats.increment_index(len(req.chunks))

    return {"status": "ok", "qdrant": len(points), "opensearch": len(os_docs)}


@router.post("/index/commit_tus")
async def commit_tus(
    body: dict[str, Any],
    *,
    x_api_key: str | None = Header(default=None),
    context: AppContext = Depends(provide_context),
) -> dict[str, Any]:
    tenant_id = body.get("tenant_id", "default")
    context.api_keys.enforce(tenant_id, x_api_key)

    repo_id = body.get("repo_id")
    chunk = body.get("chunk", {})
    tus_key = body.get("tus_key")
    assert repo_id and chunk and tus_key, "invalid payload"

    object_key = f"uploads/{tus_key}"
    text = get_object_text(object_key)
    vector = context.embedding_cache.encode(text)

    payload = {
        "chunk_id": chunk["chunk_id"],
        "repo_id": repo_id,
        "path_tokens": chunk["path_tokens"],
        "line_start": chunk.get("line_start", 1),
        "line_end": chunk.get("line_end", 1),
        "lang": chunk.get("lang"),
    }
    if chunk.get("rel_path"):
        payload["rel_path"] = chunk["rel_path"]

    context.qdrant.upsert_tenant(
        tenant_id,
        [
            PointStruct(
                id=chunk["chunk_id"],
                vector=vector,
                payload=payload,
            )
        ],
    )

    if repo_id not in settings.privacy_repo_ids:
        context.opensearch.bulk_upsert_tenant(
            tenant_id,
            [
                {
                    "chunk_id": chunk["chunk_id"],
                    "repo_id": repo_id,
                    "path_tokens": chunk["path_tokens"],
                    "rel_path": payload.get("rel_path", ""),
                    "lang": payload.get("lang"),
                    "line_start": payload["line_start"],
                    "line_end": payload["line_end"],
                    "text": text,
                }
            ],
        )

    return {"status": "ok", "chunk_id": chunk["chunk_id"]}
