"""ASGI entry point: builds the auth-wrapped MCP app to mount in FastAPI.

Returns a direct ASGI app (the ``MCPAuthApp`` wrapper around FastMCP's
streamable-HTTP Starlette app) — not a separate Starlette wrapper. This avoids
a brittle middleware-stack ordering that surfaces as path-rewriting bugs when
FastAPI ``app.mount("/mcp", ...)`` interacts with Starlette's
``Middleware()`` instantiation.
"""
from __future__ import annotations

from app.mcp.middleware import MCPAuthApp
from app.mcp.server import build_mcp_server


def build_mcp_asgi_app() -> MCPAuthApp:
    """Return an ASGI app exposing FastMCP behind API-key authentication.

    The returned object also has a ``.router`` attribute that exposes the
    inner FastMCP Starlette router so the parent FastAPI app can forward the
    streamable-HTTP session manager's lifespan into its own lifespan context.
    """
    mcp = build_mcp_server()
    inner = mcp.streamable_http_app()
    return MCPAuthApp(inner)
