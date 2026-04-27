"""Starlette middleware that authenticates MCP requests via API key."""
from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.db.database import async_session_factory
from app.mcp.keys import parse_bearer, verify_api_key

logger = logging.getLogger(__name__)


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Reject any request that doesn't carry a valid Miriade API key.

    Accepts the key via either:
      - `Authorization: Bearer mir_...`
      - `x-api-key: mir_...`

    Attaches the verified `ApiKey` row to `request.state.api_key` so downstream
    tools can read `client_tag` / `scopes` if needed.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        raw = parse_bearer(request.headers.get("authorization"))
        if not raw:
            raw = (request.headers.get("x-api-key") or "").strip() or None

        if not raw:
            return JSONResponse(
                {"error": "unauthorized", "detail": "Missing API key"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="miriade-mcp"'},
            )

        async with async_session_factory() as db:
            try:
                key = await verify_api_key(db, raw)
            except Exception as e:
                logger.exception("API key verification failed: %s", e)
                return JSONResponse(
                    {"error": "server_error", "detail": "Key verification failed"},
                    status_code=500,
                )

        if key is None:
            return JSONResponse(
                {"error": "unauthorized", "detail": "Invalid or revoked API key"},
                status_code=401,
            )

        request.state.api_key_id = key.id
        request.state.api_key_client_tag = key.client_tag
        request.state.api_key_scopes = key.scopes or []
        return await call_next(request)
