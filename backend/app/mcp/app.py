"""ASGI entry point: builds the MCP Starlette app with auth middleware."""
from __future__ import annotations

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount

from app.mcp.middleware import ApiKeyAuthMiddleware
from app.mcp.server import build_mcp_server


def build_mcp_asgi_app() -> Starlette:
    """Return a Starlette app exposing the MCP server over streamable HTTP.

    Protected by `ApiKeyAuthMiddleware`. Mounted by the main FastAPI app at `/mcp`
    so the full public URL for MCP clients is `https://<host>/mcp/`.
    """
    mcp = build_mcp_server()
    inner = mcp.streamable_http_app()

    return Starlette(
        middleware=[Middleware(ApiKeyAuthMiddleware)],
        routes=[Mount("/", app=inner)],
        lifespan=inner.router.lifespan_context,
    )
