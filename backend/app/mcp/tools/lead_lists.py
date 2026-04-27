"""MCP tools: lead lists."""
from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func as sa_func, select, update

from app.mcp.session import db_session
from app.mcp.tools._common import lead_list_to_dict, person_to_dict, company_to_dict
from app.models.lead_list import LeadList
from app.models.person import Person
from app.models.company import Company


async def _refresh_counts(db, list_id: int) -> None:
    p = (await db.execute(select(sa_func.count()).where(Person.list_id == list_id))).scalar() or 0
    c = (await db.execute(select(sa_func.count()).where(Company.list_id == list_id))).scalar() or 0
    await db.execute(update(LeadList).where(LeadList.id == list_id).values(people_count=p, companies_count=c))


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_lead_lists(
        ai_agent_id: Optional[int] = None,
        client_tag: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List lead lists, optionally filtered by AI agent or client tag."""
        async with db_session() as db:
            q = select(LeadList)
            if ai_agent_id is not None:
                q = q.where(LeadList.ai_agent_id == ai_agent_id)
            if client_tag is not None:
                q = q.where(LeadList.client_tag.ilike(f"%{client_tag}%"))
            rows = (await db.execute(q.order_by(LeadList.created_at.desc()).offset(skip).limit(limit))).scalars().all()
        return {"lists": [lead_list_to_dict(r) for r in rows], "total": len(rows)}

    @mcp.tool()
    async def get_lead_list(list_id: int) -> dict[str, Any]:
        """Fetch a lead list by ID."""
        async with db_session() as db:
            ll = await db.get(LeadList, list_id)
            if not ll:
                return {"error": "not_found", "list_id": list_id}
            return lead_list_to_dict(ll)

    @mcp.tool()
    async def create_lead_list(
        name: str,
        description: Optional[str] = None,
        client_tag: Optional[str] = None,
        ai_agent_id: Optional[int] = None,
        filters_snapshot: Optional[dict] = None,
        person_ids: Optional[list[int]] = None,
        company_ids: Optional[list[int]] = None,
    ) -> dict[str, Any]:
        """Create a lead list and optionally populate it with existing people/companies."""
        async with db_session() as db:
            ll = LeadList(
                name=name, description=description, client_tag=client_tag,
                ai_agent_id=ai_agent_id, filters_snapshot=filters_snapshot,
            )
            db.add(ll)
            await db.flush()

            if person_ids:
                await db.execute(update(Person).where(Person.id.in_(person_ids)).values(list_id=ll.id))
            if company_ids:
                await db.execute(update(Company).where(Company.id.in_(company_ids)).values(list_id=ll.id))
            await _refresh_counts(db, ll.id)
            await db.refresh(ll)
            return lead_list_to_dict(ll)

    @mcp.tool()
    async def update_lead_list(
        list_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        client_tag: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update lead list metadata."""
        async with db_session() as db:
            ll = await db.get(LeadList, list_id)
            if not ll:
                return {"error": "not_found", "list_id": list_id}
            if name is not None:
                ll.name = name
            if description is not None:
                ll.description = description
            if client_tag is not None:
                ll.client_tag = client_tag
            await db.flush()
            await db.refresh(ll)
            return lead_list_to_dict(ll)

    @mcp.tool()
    async def delete_lead_list(list_id: int) -> dict[str, Any]:
        """Delete a lead list. People/companies are not deleted — only detached (list_id set NULL)."""
        async with db_session() as db:
            ll = await db.get(LeadList, list_id)
            if not ll:
                return {"error": "not_found", "list_id": list_id}
            await db.execute(update(Person).where(Person.list_id == list_id).values(list_id=None))
            await db.execute(update(Company).where(Company.list_id == list_id).values(list_id=None))
            await db.delete(ll)
            return {"deleted": True, "list_id": list_id}

    @mcp.tool()
    async def add_people_to_list(list_id: int, person_ids: list[int]) -> dict[str, Any]:
        """Attach people to a lead list (overwrites any previous list_id on those rows)."""
        if not person_ids:
            return {"added": 0}
        async with db_session() as db:
            ll = await db.get(LeadList, list_id)
            if not ll:
                return {"error": "not_found", "list_id": list_id}
            res = await db.execute(update(Person).where(Person.id.in_(person_ids)).values(list_id=list_id))
            await _refresh_counts(db, list_id)
            return {"added": res.rowcount or 0, "list_id": list_id}

    @mcp.tool()
    async def remove_people_from_list(list_id: int, person_ids: list[int]) -> dict[str, Any]:
        """Detach people from a lead list (sets list_id NULL on matched rows)."""
        if not person_ids:
            return {"removed": 0}
        async with db_session() as db:
            res = await db.execute(
                update(Person)
                .where(Person.id.in_(person_ids), Person.list_id == list_id)
                .values(list_id=None)
            )
            await _refresh_counts(db, list_id)
            return {"removed": res.rowcount or 0, "list_id": list_id}

    @mcp.tool()
    async def add_companies_to_list(list_id: int, company_ids: list[int]) -> dict[str, Any]:
        """Attach companies to a lead list."""
        if not company_ids:
            return {"added": 0}
        async with db_session() as db:
            ll = await db.get(LeadList, list_id)
            if not ll:
                return {"error": "not_found", "list_id": list_id}
            res = await db.execute(update(Company).where(Company.id.in_(company_ids)).values(list_id=list_id))
            await _refresh_counts(db, list_id)
            return {"added": res.rowcount or 0, "list_id": list_id}

    @mcp.tool()
    async def list_people_in_list(list_id: int, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        """Paginate people that belong to a given lead list."""
        page = max(page, 1)
        page_size = max(1, min(page_size, 500))
        async with db_session() as db:
            q = select(Person).where(Person.list_id == list_id)
            total = (await db.execute(select(sa_func.count()).select_from(q.subquery()))).scalar() or 0
            rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
        return {
            "people": [person_to_dict(p) for p in rows],
            "total": total, "page": page, "page_size": page_size,
        }

    @mcp.tool()
    async def list_companies_in_list(list_id: int, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        """Paginate companies that belong to a given lead list."""
        page = max(page, 1)
        page_size = max(1, min(page_size, 500))
        async with db_session() as db:
            q = select(Company).where(Company.list_id == list_id)
            total = (await db.execute(select(sa_func.count()).select_from(q.subquery()))).scalar() or 0
            rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
        return {
            "companies": [company_to_dict(c) for c in rows],
            "total": total, "page": page, "page_size": page_size,
        }
