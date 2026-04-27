"""ASGI middleware that authenticates MCP requests via API key.

Three places the key may live (checked in order):
  1. URL path prefix: ``/mir_xxxx/...`` — convenient for clients that don't
     allow custom request headers (e.g. Claude.ai web "Custom Connectors").
     The prefix is stripped before the request is forwarded to FastMCP.
  2. ``Authorization: Bearer mir_...``
  3. ``x-api-key: mir_...``

The verified ``ApiKey`` is attached to ``scope["state"]`` so downstream tools
can read ``client_tag`` / ``scopes`` if they need to scope queries.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.db.database import async_session_factory
from app.mcp.keys import KEY_PREFIX, parse_bearer, verify_api_key

logger = logging.getLogger(__name__)


class ApiKeyAuthMiddleware:
    """Pure-ASGI middleware so we can mutate ``scope["path"]`` for path-prefix auth.

    Starlette's ``BaseHTTPMiddleware`` rebuilds the request and discards path
    mutations, which is why this is implemented at the ASGI level.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("method", "") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        scope = dict(scope)
        scope["state"] = dict(scope.get("state") or {})

        logger.info(
            "MCP auth: method=%s path=%r root_path=%r raw_path=%r",
            scope.get("method"),
            scope.get("path"),
            scope.get("root_path"),
            scope.get("raw_path"),
        )

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
        await self.app(scope, receive, send)

    @staticmethod
    def _extract_key_from_path(scope: dict) -> tuple[str | None, dict]:
        path = scope.get("path") or ""
        parts = path.lstrip("/").split("/", 1)
        if not parts or not parts[0].startswith(KEY_PREFIX):
            return None, scope

        raw_key = parts[0]
        new_path = "/" + (parts[1] if len(parts) > 1 else "")
        scope["path"] = new_path
        if "raw_path" in scope:
            scope["raw_path"] = new_path.encode("utf-8")
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
