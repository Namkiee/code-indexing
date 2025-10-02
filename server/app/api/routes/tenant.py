"""Tenant-related endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.utils.vault import get_current_salt

router = APIRouter(prefix="/v1")


@router.get("/tenant/salt")
async def get_tenant_salt(tenant_id: str = "default") -> dict[str, object]:
    salt = get_current_salt(tenant_id)
    if not salt:
        return {"tenant_id": tenant_id, "salt_ver": 0, "salt": ""}
    return {
        "tenant_id": tenant_id,
        "salt_ver": salt.get("ver", 0),
        "salt": salt.get("value", ""),
    }
