"""API key generation, hashing, and verification."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey

KEY_PREFIX = "mir_"
HASH_ALGO = "sha256"


def generate_raw_key() -> str:
    """Generate a new plaintext API key (returned once, never stored)."""
    return f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_key(raw_key: str) -> str:
    """Hash a raw API key for storage/lookup (sha256 — keys are high-entropy)."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def parse_bearer(header_value: Optional[str]) -> Optional[str]:
    """Extract the token from an Authorization header value.

    Accepts either `Bearer <token>` or a bare `<token>`.
    """
    if not header_value:
        return None
    value = header_value.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip() or None
    return value or None


async def verify_api_key(db: AsyncSession, raw_key: str) -> Optional[ApiKey]:
    """Look up an active, non-expired API key by its plaintext value.

    Returns the `ApiKey` row on success, `None` otherwise. Updates `last_used_at`.
    """
    if not raw_key or not raw_key.startswith(KEY_PREFIX):
        return None

    digest = hash_key(raw_key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == digest, ApiKey.is_active.is_(True))
    )
    key = result.scalar_one_or_none()
    if key is None:
        return None

    now = datetime.now(timezone.utc)
    if key.expires_at is not None and key.expires_at <= now:
        return None
    if key.revoked_at is not None:
        return None

    await db.execute(
        update(ApiKey).where(ApiKey.id == key.id).values(last_used_at=now)
    )
    await db.commit()
    return key
