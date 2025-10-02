"""API key enforcement helpers."""

from __future__ import annotations

from typing import Iterable

from fastapi import HTTPException


class APIKeyValidator:
    def __init__(self, tenant_keys: dict[str, Iterable[str]], require_api_key: bool) -> None:
        self._tenant_keys = {
            tenant: set(keys)
            for tenant, keys in (tenant_keys or {}).items()
        }
        self._require = require_api_key

    def enforce(self, tenant_id: str, api_key: str | None) -> None:
        if not self._require:
            return
        if not api_key:
            raise HTTPException(status_code=401, detail="missing x-api-key")
        allowed = self._tenant_keys.get(tenant_id, set())
        if api_key not in allowed:
            raise HTTPException(status_code=403, detail="invalid api key")
