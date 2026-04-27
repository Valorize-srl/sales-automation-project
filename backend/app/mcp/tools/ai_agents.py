"""MCP tools: AI Agents (client-specific configuration + knowledge base)."""
from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.mcp.session import db_session
from app.mcp.tools._common import ai_agent_to_dict
from app.models.ai_agent import AIAgent


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_ai_agents(
        client_tag: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> dict[str, Any]:
        """List AI agents with optional filters."""
        async with db_session() as db:
            q = select(AIAgent).order_by(AIAgent.created_at.desc())
            if client_tag is not None:
                q = q.where(AIAgent.client_tag == client_tag)
            if is_active is not None:
                q = q.where(AIAgent.is_active.is_(is_active))
            rows = (await db.execute(q)).scalars().all()
        return {"agents": [ai_agent_to_dict(a) for a in rows], "total": len(rows)}

    @mcp.tool()
    async def get_ai_agent(agent_id: int) -> dict[str, Any]:
        """Fetch an AI agent by ID."""
        async with db_session() as db:
            a = await db.get(AIAgent, agent_id)
            if not a:
                return {"error": "not_found", "agent_id": agent_id}
            return ai_agent_to_dict(a)

    @mcp.tool()
    async def create_ai_agent(
        name: str,
        client_tag: str,
        icp_config: dict,
        description: Optional[str] = None,
        signals_config: Optional[dict] = None,
        knowledge_base_text: Optional[str] = None,
        apollo_credits_allocated: int = 1000,
    ) -> dict[str, Any]:
        """Create a new AI agent for a client.

        `icp_config` example: {"industry": "Wine", "company_size": "10-50", "job_titles": "CEO, Founder"}.
        """
        async with db_session() as db:
            a = AIAgent(
                name=name,
                client_tag=client_tag,
                description=description,
                icp_config=icp_config,
                signals_config=signals_config,
                knowledge_base_text=knowledge_base_text,
                knowledge_base_source="manual" if knowledge_base_text else None,
                apollo_credits_allocated=apollo_credits_allocated,
            )
            db.add(a)
            await db.flush()
            await db.refresh(a)
            return ai_agent_to_dict(a)

    @mcp.tool()
    async def update_ai_agent(
        agent_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        icp_config: Optional[dict] = None,
        signals_config: Optional[dict] = None,
        apollo_credits_allocated: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Partial update on AI agent configuration."""
        async with db_session() as db:
            a = await db.get(AIAgent, agent_id)
            if not a:
                return {"error": "not_found", "agent_id": agent_id}
            if name is not None:
                a.name = name
            if description is not None:
                a.description = description
            if icp_config is not None:
                a.icp_config = icp_config
            if signals_config is not None:
                a.signals_config = signals_config
            if apollo_credits_allocated is not None:
                a.apollo_credits_allocated = apollo_credits_allocated
            if is_active is not None:
                a.is_active = is_active
            await db.flush()
            await db.refresh(a)
            return ai_agent_to_dict(a)

    @mcp.tool()
    async def update_knowledge_base(
        agent_id: int,
        knowledge_base_text: str,
        source: str = "manual",
    ) -> dict[str, Any]:
        """Replace the agent's knowledge base text. `source` is free-form (e.g. manual/url/upload)."""
        async with db_session() as db:
            a = await db.get(AIAgent, agent_id)
            if not a:
                return {"error": "not_found", "agent_id": agent_id}
            a.knowledge_base_text = knowledge_base_text
            a.knowledge_base_source = source
            await db.flush()
            await db.refresh(a)
            return ai_agent_to_dict(a)

    @mcp.tool()
    async def delete_ai_agent(agent_id: int) -> dict[str, Any]:
        """Delete an AI agent. Associated lead lists are unlinked (ON DELETE SET NULL)."""
        async with db_session() as db:
            a = await db.get(AIAgent, agent_id)
            if not a:
                return {"error": "not_found", "agent_id": agent_id}
            await db.delete(a)
            return {"deleted": True, "agent_id": agent_id}
