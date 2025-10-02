"""Metrics endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.context import AppContext
from app.api.deps import provide_context

router = APIRouter(prefix="/v1")


@router.get("/metrics")
async def metrics(context: AppContext = Depends(provide_context)) -> dict[str, object]:
    return context.stats.snapshot()
