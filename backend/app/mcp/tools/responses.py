"""MCP tools: email responses (inbox), sentiment and AI replies."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func as sa_func, select

from app.mcp.session import db_session
from app.mcp.tools._common import response_to_dict
from app.models.email_response import EmailResponse, MessageDirection, ResponseStatus, Sentiment


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_responses(
        campaign_id: Optional[int] = None,
        sentiment: Optional[str] = None,
        status: Optional[str] = None,
        direction: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """List email responses with filters. Dates accept ISO 8601."""
        page = max(page, 1)
        page_size = max(1, min(page_size, 200))

        async with db_session() as db:
            q = select(EmailResponse).order_by(EmailResponse.received_at.desc().nullslast())
            if campaign_id is not None:
                q = q.where(EmailResponse.campaign_id == campaign_id)
            if sentiment:
                try:
                    q = q.where(EmailResponse.sentiment == Sentiment(sentiment))
                except ValueError:
                    return {"error": "invalid_sentiment", "allowed": [s.value for s in Sentiment]}
            if status:
                try:
                    q = q.where(EmailResponse.status == ResponseStatus(status))
                except ValueError:
                    return {"error": "invalid_status", "allowed": [s.value for s in ResponseStatus]}
            if direction:
                try:
                    q = q.where(EmailResponse.direction == MessageDirection(direction))
                except ValueError:
                    return {"error": "invalid_direction", "allowed": [d.value for d in MessageDirection]}
            fd = _parse_date(from_date)
            td = _parse_date(to_date)
            if fd:
                q = q.where(EmailResponse.received_at >= fd)
            if td:
                q = q.where(EmailResponse.received_at <= td)

            total = (await db.execute(select(sa_func.count()).select_from(q.subquery()))).scalar() or 0
            rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()

        return {
            "responses": [response_to_dict(r) for r in rows],
            "total": total, "page": page, "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 1,
        }

    @mcp.tool()
    async def get_response(response_id: int) -> dict[str, Any]:
        """Fetch a single email response by ID."""
        async with db_session() as db:
            r = await db.get(EmailResponse, response_id)
            if not r:
                return {"error": "not_found", "response_id": response_id}
            return response_to_dict(r)

    @mcp.tool()
    async def generate_ai_reply(
        response_id: int,
        ai_agent_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Generate an AI-suggested reply using the agent's knowledge base.

        Stores the suggestion on the response and returns `{subject, body, tone, call_to_action}`.
        """
        from app.services.ai_replier import get_ai_replier_service

        async with db_session() as db:
            service = await get_ai_replier_service(db)
            try:
                return await service.generate_reply(
                    email_response_id=response_id, ai_agent_id=ai_agent_id
                )
            except ValueError as e:
                return {"error": "not_found", "detail": str(e)}
            except Exception as e:
                return {"error": "generation_failed", "detail": str(e)}

    @mcp.tool()
    async def approve_and_send_reply(
        response_id: int,
        approved_body: str,
        approved_subject: Optional[str] = None,
        sender_email: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send an approved reply via Instantly and mark the response as SENT."""
        from app.services.ai_replier import get_ai_replier_service

        async with db_session() as db:
            service = await get_ai_replier_service(db)
            try:
                return await service.approve_and_send_reply(
                    email_response_id=response_id,
                    approved_body=approved_body,
                    approved_subject=approved_subject,
                    sender_email=sender_email,
                )
            except ValueError as e:
                return {"error": "not_found", "detail": str(e)}
            except Exception as e:
                return {"error": "send_failed", "detail": str(e)}

    @mcp.tool()
    async def approve_reply_without_sending(
        response_id: int,
        approved_body: str,
        approved_subject: Optional[str] = None,
    ) -> dict[str, Any]:
        """Mark the reply as approved (HUMAN_APPROVED) without sending it — useful for review queues."""
        from app.services.ai_replier import get_ai_replier_service

        async with db_session() as db:
            service = await get_ai_replier_service(db)
            try:
                r = await service.approve_reply_without_sending(
                    email_response_id=response_id,
                    approved_body=approved_body,
                    approved_subject=approved_subject,
                )
                return response_to_dict(r)
            except Exception as e:
                return {"error": "failed", "detail": str(e)}

    @mcp.tool()
    async def ignore_response(response_id: int) -> dict[str, Any]:
        """Mark a response as IGNORED (no reply will be sent)."""
        from app.services.ai_replier import get_ai_replier_service

        async with db_session() as db:
            service = await get_ai_replier_service(db)
            try:
                r = await service.ignore_response(email_response_id=response_id)
                return response_to_dict(r)
            except Exception as e:
                return {"error": "failed", "detail": str(e)}
