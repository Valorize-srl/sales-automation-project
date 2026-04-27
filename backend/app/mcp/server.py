"""FastMCP server instance with all Miriade tools registered."""
from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def build_mcp_server() -> FastMCP:
    """Construct a FastMCP instance and register all tool groups."""
    mcp = FastMCP(
        name="miriade",
        instructions=(
            "Miriade Sales Automation Platform MCP server. "
            "Exposes full read/write access to leads (people & companies), lead lists, "
            "email campaigns (Instantly-synced), AI agents, email responses with sentiment "
            "analysis and AI reply generation, Apollo.io prospecting, and usage analytics. "
            "Every action is scoped to the authenticated API key's client_tag when present."
        ),
    )

    # Lazy imports so tool registration happens once, on server construction,
    # and registration order is deterministic regardless of import order.
    from app.mcp.tools import (
        people as _people,
        companies as _companies,
        lead_lists as _lead_lists,
        campaigns as _campaigns,
        responses as _responses,
        ai_agents as _ai_agents,
        apollo as _apollo,
        analytics as _analytics,
    )

    for module in (
        _people,
        _companies,
        _lead_lists,
        _campaigns,
        _responses,
        _ai_agents,
        _apollo,
        _analytics,
    ):
        module.register(mcp)

    try:
        tool_count = len(getattr(getattr(mcp, "_tool_manager", None), "_tools", {}))
        logger.info("MCP server built with %d tools", tool_count)
    except Exception:
        logger.info("MCP server built (tool count unavailable)")
    return mcp
