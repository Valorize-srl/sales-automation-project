"""Admin API for managing MCP API keys.

All endpoints require the `MCP_MASTER_KEY` env var to be configured and passed
via the `x-master-key` header. The raw API key is returned ONLY ONCE — on
creation — and never stored in plaintext.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.mcp.keys import generate_raw_key, hash_key
from app.models.api_key import ApiKey

logger = logging.getLogger(__name__)
router = APIRouter()


async def require_master_key(x_master_key: Optional[str] = Header(default=None)) -> None:
    if not settings.mcp_master_key:
        raise HTTPException(status_code=503, detail="MCP master key is not configured")
    if not x_master_key or x_master_key != settings.mcp_master_key:
        raise HTTPException(status_code=401, detail="Invalid master key")


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    client_tag: Optional[str] = Field(default=None, max_length=200)
    scopes: Optional[list[str]] = None
    expires_at: Optional[datetime] = None


class ApiKeyOut(BaseModel):
    id: int
    name: str
    prefix: str
    last_four: str
    client_tag: Optional[str]
    scopes: Optional[list[str]]
    is_active: bool
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
    revoked_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ApiKeyCreateOut(ApiKeyOut):
    raw_key: str = Field(description="Plaintext key — shown once, store it now")


@router.post("", response_model=ApiKeyCreateOut, status_code=201)
async def create_api_key(
    data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_master_key),
):
    """Create a new API key. The plaintext `raw_key` is returned ONLY here."""
    raw = generate_raw_key()
    digest = hash_key(raw)
    prefix = raw[:8]
    last_four = raw[-4:]

    key = ApiKey(
        name=data.name,
        key_hash=digest,
        prefix=prefix,
        last_four=last_four,
        client_tag=data.client_tag,
        scopes=data.scopes,
        expires_at=data.expires_at,
    )
    db.add(key)
    await db.flush()
    await db.refresh(key)

    payload = ApiKeyOut.model_validate(key).model_dump()
    payload["raw_key"] = raw
    return payload


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    include_revoked: bool = False,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_master_key),
):
    """List existing API keys (without the plaintext value)."""
    q = select(ApiKey).order_by(ApiKey.created_at.desc())
    if not include_revoked:
        q = q.where(ApiKey.is_active.is_(True))
    rows = (await db.execute(q)).scalars().all()
    return rows


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_master_key),
):
    """Revoke an API key (sets is_active=False, revoked_at=now)."""
    k = await db.get(ApiKey, key_id)
    if not k:
        raise HTTPException(status_code=404, detail="API key not found")
    k.is_active = False
    k.revoked_at = datetime.now(timezone.utc)
