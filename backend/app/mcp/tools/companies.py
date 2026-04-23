"""MCP tools: companies."""
from __future__ import annotations

import math
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import delete as sql_delete, func as sa_func, select

from app.mcp.session import db_session
from app.mcp.tools._common import company_to_dict
from app.models.company import Company


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_companies(
        search: Optional[str] = None,
        industry: Optional[str] = None,
        client_tag: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """List companies with optional search (by name/domain), industry and client_tag filters."""
        page = max(page, 1)
        page_size = max(1, min(page_size, 200))

        async with db_session() as db:
            q = select(Company)
            if search:
                q = q.where(
                    Company.name.ilike(f"%{search}%") | Company.email_domain.ilike(f"%{search}%")
                )
            if industry is not None:
                q = q.where(Company.industry == industry)
            if client_tag is not None:
                q = q.where(Company.client_tag.ilike(f"%{client_tag}%"))

            total = (await db.execute(select(sa_func.count()).select_from(q.subquery()))).scalar() or 0
            data = (await db.execute(
                q.order_by(Company.name.asc()).offset((page - 1) * page_size).limit(page_size)
            )).scalars().all()

        return {
            "companies": [company_to_dict(c) for c in data],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 1,
        }

    @mcp.tool()
    async def get_company(company_id: int) -> dict[str, Any]:
        """Fetch a single company by ID."""
        async with db_session() as db:
            c = await db.get(Company, company_id)
            if not c:
                return {"error": "not_found", "company_id": company_id}
            return company_to_dict(c)

    @mcp.tool()
    async def create_company(
        name: str,
        website: Optional[str] = None,
        email: Optional[str] = None,
        email_domain: Optional[str] = None,
        phone: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        industry: Optional[str] = None,
        location: Optional[str] = None,
        signals: Optional[str] = None,
        notes: Optional[str] = None,
        client_tag: Optional[str] = None,
        tags: Optional[list[str]] = None,
        list_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create a new company record."""
        async with db_session() as db:
            c = Company(
                name=name, website=website, email=email, email_domain=email_domain,
                phone=phone, linkedin_url=linkedin_url, industry=industry, location=location,
                signals=signals, notes=notes, client_tag=client_tag, tags=tags, list_id=list_id,
            )
            db.add(c)
            await db.flush()
            await db.refresh(c)
            return company_to_dict(c)

    @mcp.tool()
    async def update_company(
        company_id: int,
        name: Optional[str] = None,
        website: Optional[str] = None,
        email: Optional[str] = None,
        email_domain: Optional[str] = None,
        phone: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        industry: Optional[str] = None,
        location: Optional[str] = None,
        signals: Optional[str] = None,
        notes: Optional[str] = None,
        client_tag: Optional[str] = None,
        tags: Optional[list[str]] = None,
        list_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Partial update. Pass only the fields you want to change."""
        async with db_session() as db:
            c = await db.get(Company, company_id)
            if not c:
                return {"error": "not_found", "company_id": company_id}

            updates = {
                "name": name, "website": website, "email": email, "email_domain": email_domain,
                "phone": phone, "linkedin_url": linkedin_url, "industry": industry,
                "location": location, "signals": signals, "notes": notes,
                "client_tag": client_tag, "tags": tags, "list_id": list_id,
            }
            for field, value in updates.items():
                if value is not None:
                    setattr(c, field, value)
            await db.flush()
            await db.refresh(c)
            return company_to_dict(c)

    @mcp.tool()
    async def delete_company(company_id: int) -> dict[str, Any]:
        """Delete a company permanently."""
        async with db_session() as db:
            c = await db.get(Company, company_id)
            if not c:
                return {"error": "not_found", "company_id": company_id}
            await db.delete(c)
            return {"deleted": True, "company_id": company_id}

    @mcp.tool()
    async def bulk_delete_companies(company_ids: list[int]) -> dict[str, Any]:
        """Delete many companies at once. Returns deleted count."""
        if not company_ids:
            return {"deleted_count": 0}
        async with db_session() as db:
            res = await db.execute(sql_delete(Company).where(Company.id.in_(company_ids)))
            return {"deleted_count": res.rowcount or 0}
