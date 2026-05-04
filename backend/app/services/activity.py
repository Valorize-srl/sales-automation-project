"""Helpers to write structured activity_log entries.

Designed to be cheap and forgiving: a logging error never blocks the operation
that triggered it. Callers pass the existing ``AsyncSession`` so the log entry
is part of the same transaction as the action being recorded.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog

logger = logging.getLogger(__name__)


async def log_activity(
    db: AsyncSession,
    *,
    target_type: str,
    target_id: int,
    action: str,
    payload: Optional[dict[str, Any]] = None,
    actor: Optional[str] = None,
) -> None:
    """Append a single ActivityLog row. Swallows exceptions."""
    try:
        db.add(ActivityLog(
            target_type=target_type,
            target_id=target_id,
            action=action,
            payload=payload,
            actor=actor or "system",
        ))
    except Exception as e:
        logger.warning("Failed to write activity_log entry: %s", e)


async def log_field_changes(
    db: AsyncSession,
    *,
    target_type: str,
    target_id: int,
    updates: dict[str, Any],
    actor: Optional[str] = None,
) -> None:
    """Convenience helper for CRUD updates: writes one entry summarising the
    field-level diff."""
    if not updates:
        return
    await log_activity(
        db, target_type=target_type, target_id=target_id,
        action="field_updated",
        payload={"changed_keys": sorted(updates.keys()), "values": updates},
        actor=actor,
    )


def diff_for_log(before: dict, after: dict, keys: Iterable[str]) -> dict[str, Any]:
    """Compute the subset of ``after`` whose values differ from ``before`` on
    the given ``keys``. Used by handlers that have both shapes to record only
    the actual changes."""
    out: dict[str, Any] = {}
    for k in keys:
        if before.get(k) != after.get(k):
            out[k] = {"from": before.get(k), "to": after.get(k)}
    return out
