"""MCP tools: activity log."""
from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select, func as sa_func

from app.mcp.session import db_session
from app.models.activity_log import ActivityLog


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_activity(
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Read the activity timeline. Filter by target ('account' or 'contact'),
        target_id, action (field_updated, scored, email_verified, …), or actor."""
        page = max(1, page)
        page_size = max(1, min(200, page_size))
        async with db_session() as db:
            q = select(ActivityLog).order_by(ActivityLog.created_at.desc())
            if target_type:
                q = q.where(ActivityLog.target_type == target_type)
            if target_id is not None:
                q = q.where(ActivityLog.target_id == target_id)
            if action:
                q = q.where(ActivityLog.action == action)
            if actor:
                q = q.where(ActivityLog.actor == actor)
            total = (await db.execute(select(sa_func.count()).select_from(q.subquery()))).scalar() or 0
            rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
        return {
            "activities": [
                {
                    "id": r.id, "target_type": r.target_type, "target_id": r.target_id,
                    "action": r.action, "payload": r.payload, "actor": r.actor,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
            "total": total, "page": page, "page_size": page_size,
        }
