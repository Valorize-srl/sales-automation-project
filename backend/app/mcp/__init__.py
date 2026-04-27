"""MCP (Model Context Protocol) server for Miriade.

Exposes Miriade's core operations as MCP tools so Claude (Desktop, Code, Agent SDK)
and other MCP-compatible clients can interact with the platform via a single
authenticated endpoint.

Entry point: `app.mcp.app.build_mcp_asgi_app()` returns a Starlette app that the
main FastAPI application mounts at `/mcp`.
"""
from app.mcp.app import build_mcp_asgi_app

__all__ = ["build_mcp_asgi_app"]
