"""DB session helper for MCP tools.

MCP tools are plain async functions (not FastAPI path operations), so they can't
use `Depends(get_db)`. This helper provides an async context manager that yields
an `AsyncSession` with commit-on-success / rollback-on-error semantics matching
the behaviour of `get_db`.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_factory


@asynccontextmanager
async def db_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
