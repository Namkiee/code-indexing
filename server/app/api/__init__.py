"""API router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import feedback, index, metrics, search, tenant

api_router = APIRouter()
api_router.include_router(tenant.router)
api_router.include_router(index.router)
api_router.include_router(search.router)
api_router.include_router(feedback.router)
api_router.include_router(metrics.router)
