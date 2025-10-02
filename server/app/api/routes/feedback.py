"""Feedback endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from app.api.context import AppContext
from app.api.deps import provide_context
from app.models.schemas import FeedbackRequest, FeedbackResponse
from app.utils.jsonl import append_jsonl

router = APIRouter(prefix="/v1")


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(
    req: FeedbackRequest,
    *,
    context: AppContext = Depends(provide_context),
) -> FeedbackResponse:
    append_jsonl(
        "/app/server/data/feedback_log.jsonl",
        {
            "search_id": req.search_id,
            "clicked_chunk_id": req.clicked_chunk_id,
            "grade": int(req.grade),
            "timestamp": time.time(),
        },
    )
    context.stats.increment_feedback()
    return FeedbackResponse(status="ok")
