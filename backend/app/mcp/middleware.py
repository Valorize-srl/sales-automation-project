"""ASGI app that authenticates MCP requests via API key.

Three places the key may live (checked in order):
  1. URL path: any path segment starting with ``mir_`` is treated as the key.
     Convenient for clients that don't allow custom request headers (e.g.
     Claude.ai web "Custom Connectors"). The segment is consumed and the path
     forwarded to the inner FastMCP app is rewritten to ``/`` so the
     streamable-HTTP route always matches.
  2. ``Authorization: Bearer mir_...`` header.
  3. ``x-api-key: mir_...`` header.

The verified ``ApiKey`` is attached to ``scope["state"]`` so downstream tools
can read ``client_tag`` / ``scopes`` if they need to scope queries.

This is implemented as a direct ASGI wrapper around FastMCP's streamable-HTTP
Starlette app — without an intermediate Starlette layer — so we have full
control over scope path rewriting (Starlette's ``BaseHTTPMiddleware`` discards
path mutations, and stacking middleware via ``Middleware()`` interacts oddly
with FastAPI's ``app.mount`` semantics).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.db.database import async_session_factory
from app.mcp.keys import KEY_PREFIX, parse_bearer, verify_api_key

logger = logging.getLogger(__name__)


class MCPAuthApp:
    """Authenticate, rewrite the path, then delegate to the inner FastMCP app."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        # Expose the inner Starlette router so the parent FastAPI lifespan can
        # forward MCP's streamable-HTTP session manager startup/shutdown.
        self.router = getattr(inner, "router", None)

    async def __call__(self, scope: dict, receive, send) -> None:
        if scope["type"] != "http":
            await self.inner(scope, receive, send)
            return
        if scope.get("method", "") == "OPTIONS":
            await self.inner(scope, receive, send)
            return

        scope = dict(scope)
        scope["state"] = dict(scope.get("state") or {})

        raw_key, scope = self._extract_key_from_path(scope)
        if not raw_key:
            raw_key = self._extract_key_from_headers(scope)

        if not raw_key:
            await self._send_error(send, 401, "Missing API key")
            return

        try:
            async with async_session_factory() as db:
                key = await verify_api_key(db, raw_key)
        except Exception as e:
            logger.exception("API key verification failed: %s", e)
            await self._send_error(send, 500, "Key verification failed")
            return

        if key is None:
            await self._send_error(send, 401, "Invalid or revoked API key")
            return

        scope["state"]["api_key_id"] = key.id
        scope["state"]["api_key_client_tag"] = key.client_tag
        scope["state"]["api_key_scopes"] = key.scopes or []
        await self.inner(scope, receive, send)

    @staticmethod
    def _extract_key_from_path(scope: dict) -> tuple[str | None, dict]:
        """Pull a ``mir_xxx`` segment out of any position in the path.

        Returns the raw key (or None) and a scope where the key segment has
        been removed and the remaining path collapsed to ``/`` so the inner
        FastMCP streamable-HTTP route always matches.
        """
        path = scope.get("path") or ""
        segments = [s for s in path.split("/") if s]
        idx = next(
            (i for i, s in enumerate(segments) if s.startswith(KEY_PREFIX)),
            None,
        )
        if idx is None:
            return None, scope

        raw_key = segments[idx]
        # Always forward the inner request to "/" — that's where FastMCP's
        # streamable-HTTP transport is registered (server.py sets
        # streamable_http_path="/"). This works regardless of whether the
        # outer FastAPI mount stripped the /mcp prefix or not.
        scope["path"] = "/"
        scope["raw_path"] = b"/"
        return raw_key, scope

    @staticmethod
    def _extract_key_from_headers(scope: dict) -> str | None:
        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        raw = parse_bearer(headers.get("authorization"))
        if raw:
            return raw
        return (headers.get("x-api-key") or "").strip() or None

    @staticmethod
    async def _send_error(send, status: int, detail: str) -> None:
        body = json.dumps({"error": "unauthorized", "detail": detail}).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        if status == 401:
            headers.append((b"www-authenticate", b'Bearer realm="miriade-mcp"'))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})


# Backward-compatible alias used by other modules.
ApiKeyAuthMiddleware = MCPAuthApp
