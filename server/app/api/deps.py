"""Common FastAPI dependencies for routers."""

from __future__ import annotations

from fastapi import Depends, Request

from app.api.context import AppContext


def get_context(request: Request) -> AppContext:
    return request.app.state.context  # type: ignore[attr-defined]


def provide_context(context: AppContext = Depends(get_context)) -> AppContext:
    return context
