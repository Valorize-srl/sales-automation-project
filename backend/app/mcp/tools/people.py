"""MCP tools: people (individual contacts)."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import delete as sql_delete, func as sa_func, or_, select

from app.mcp.session import db_session
from app.mcp.tools._common import person_to_dict
from app.models.company import Company
from app.models.person import Person

logger = logging.getLogger(__name__)


async def _match_company(db, company_name: Optional[str], email: Optional[str]) -> Optional[int]:
    if company_name:
        res = await db.execute(
            select(Company.id).where(sa_func.lower(Company.name) == company_name.lower().strip())
        )
        cid = res.scalar_one_or_none()
        if cid:
            return cid
    if email and "@" in email:
        domain = email.split("@", 1)[1].lower().strip()
        res = await db.execute(select(Company.id).where(Company.email_domain == domain))
        return res.scalar_one_or_none()
    return None


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_people(
        search: Optional[str] = None,
        company_id: Optional[int] = None,
        industry: Optional[str] = None,
        client_tag: Optional[str] = None,
        has_email: Optional[bool] = None,
        has_phone: Optional[bool] = None,
        has_linkedin: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """List people (contacts) with filters and pagination.

        Filters combine with AND. Returns up to 200 per page.
        """
        page = max(page, 1)
        page_size = max(1, min(page_size, 200))

        async with db_session() as db:
            q = select(Person)
            if search:
                q = q.where(
                    sa_func.concat(Person.first_name, " ", Person.last_name).ilike(f"%{search}%")
                    | Person.email.ilike(f"%{search}%")
                )
            if company_id is not None:
                q = q.where(Person.company_id == company_id)
            if industry is not None:
                q = q.where(Person.industry == industry)
            if client_tag is not None:
                q = q.where(Person.client_tag.ilike(f"%{client_tag}%"))
            if has_email is True:
                q = q.where(Person.email.isnot(None), Person.email != "")
            elif has_email is False:
                q = q.where(or_(Person.email.is_(None), Person.email == ""))
            if has_phone is True:
                q = q.where(Person.phone.isnot(None), Person.phone != "")
            elif has_phone is False:
                q = q.where(or_(Person.phone.is_(None), Person.phone == ""))
            if has_linkedin is True:
                q = q.where(Person.linkedin_url.isnot(None), Person.linkedin_url != "")
            elif has_linkedin is False:
                q = q.where(or_(Person.linkedin_url.is_(None), Person.linkedin_url == ""))

            total = (await db.execute(select(sa_func.count()).select_from(q.subquery()))).scalar() or 0
            data_q = q.order_by(Person.last_name.asc(), Person.first_name.asc()).offset((page - 1) * page_size).limit(page_size)
            rows = (await db.execute(data_q)).scalars().all()

        return {
            "people": [person_to_dict(p) for p in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 1,
        }

    @mcp.tool()
    async def get_person(person_id: int) -> dict[str, Any]:
        """Fetch a single person by ID."""
        async with db_session() as db:
            p = await db.get(Person, person_id)
            if not p:
                return {"error": "not_found", "person_id": person_id}
            return person_to_dict(p)

    @mcp.tool()
    async def create_person(
        first_name: str,
        last_name: str,
        email: str,
        company_name: Optional[str] = None,
        title: Optional[str] = None,
        phone: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        industry: Optional[str] = None,
        location: Optional[str] = None,
        client_tag: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[list[str]] = None,
        list_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create a new person. Attempts to match company by name or email domain."""
        async with db_session() as db:
            company_id = await _match_company(db, company_name, email)
            p = Person(
                first_name=first_name,
                last_name=last_name,
                email=email.lower().strip(),
                company_name=company_name,
                company_id=company_id,
                title=title,
                phone=phone,
                linkedin_url=linkedin_url,
                industry=industry,
                location=location,
                client_tag=client_tag,
                notes=notes,
                tags=tags,
                list_id=list_id,
            )
            db.add(p)
            await db.flush()
            await db.refresh(p)
            return person_to_dict(p)

    @mcp.tool()
    async def update_person(
        person_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        company_name: Optional[str] = None,
        title: Optional[str] = None,
        phone: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        industry: Optional[str] = None,
        location: Optional[str] = None,
        client_tag: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[list[str]] = None,
        list_id: Optional[int] = None,
        converted: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Partial update. Pass only the fields you want to change."""
        async with db_session() as db:
            p = await db.get(Person, person_id)
            if not p:
                return {"error": "not_found", "person_id": person_id}

            updates = {
                "first_name": first_name, "last_name": last_name, "email": email,
                "company_name": company_name, "title": title, "phone": phone,
                "linkedin_url": linkedin_url, "industry": industry, "location": location,
                "client_tag": client_tag, "notes": notes, "tags": tags, "list_id": list_id,
            }
            for field, value in updates.items():
                if value is not None:
                    setattr(p, field, value)

            if company_name is not None:
                p.company_id = await _match_company(db, company_name, p.email)

            if converted is not None:
                p.converted_at = datetime.now(timezone.utc) if converted else None

            await db.flush()
            await db.refresh(p)
            return person_to_dict(p)

    @mcp.tool()
    async def delete_person(person_id: int) -> dict[str, Any]:
        """Delete a person permanently."""
        async with db_session() as db:
            p = await db.get(Person, person_id)
            if not p:
                return {"error": "not_found", "person_id": person_id}
            await db.delete(p)
            return {"deleted": True, "person_id": person_id}

    @mcp.tool()
    async def bulk_delete_people(person_ids: list[int]) -> dict[str, Any]:
        """Delete many people at once. Returns deleted count."""
        if not person_ids:
            return {"deleted_count": 0}
        async with db_session() as db:
            res = await db.execute(sql_delete(Person).where(Person.id.in_(person_ids)))
            return {"deleted_count": res.rowcount or 0}

    @mcp.tool()
    async def bulk_tag_people(
        person_ids: list[int],
        tags_to_add: Optional[list[str]] = None,
        tags_to_remove: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Add and/or remove tags on a set of people."""
        if not person_ids or (not tags_to_add and not tags_to_remove):
            return {"people_tagged": 0}
        async with db_session() as db:
            rows = (await db.execute(select(Person).where(Person.id.in_(person_ids)))).scalars().all()
            for p in rows:
                current = list(p.tags or [])
                if tags_to_add:
                    for t in tags_to_add:
                        if t not in current:
                            current.append(t)
                if tags_to_remove:
                    current = [t for t in current if t not in tags_to_remove]
                p.tags = current
            return {"people_tagged": len(rows)}

    @mcp.tool()
    async def import_people(
        people: list[dict[str, Any]],
        default_client_tag: Optional[str] = None,
        default_industry: Optional[str] = None,
        skip_duplicates_by_email: bool = True,
    ) -> dict[str, Any]:
        """Bulk-create people from a list of dicts.

        Each dict supports: first_name, last_name, email (required), company_name,
        title, phone, linkedin_url, industry, location, client_tag, notes, tags.
        """
        imported = 0
        duplicates_skipped = 0
        errors: list[str] = []

        async with db_session() as db:
            existing: set[str] = set()
            if skip_duplicates_by_email:
                rows = (await db.execute(select(Person.email))).all()
                existing = {r[0].lower() for r in rows if r[0]}

            for idx, row in enumerate(people):
                try:
                    email = (row.get("email") or "").strip().lower()
                    if not email:
                        errors.append(f"row {idx}: missing email")
                        continue
                    if skip_duplicates_by_email and email in existing:
                        duplicates_skipped += 1
                        continue

                    first_name = (row.get("first_name") or "Unknown").strip()
                    last_name = (row.get("last_name") or "").strip()
                    if not last_name and " " in first_name:
                        first_name, last_name = first_name.split(" ", 1)

                    company_name = row.get("company_name")
                    company_id = await _match_company(db, company_name, email)

                    p = Person(
                        first_name=first_name[:100],
                        last_name=(last_name or "Unknown")[:100],
                        email=email[:255],
                        company_name=company_name,
                        company_id=company_id,
                        title=row.get("title"),
                        phone=row.get("phone"),
                        linkedin_url=row.get("linkedin_url"),
                        industry=row.get("industry") or default_industry,
                        location=row.get("location"),
                        client_tag=row.get("client_tag") or default_client_tag,
                        notes=row.get("notes"),
                        tags=row.get("tags"),
                    )
                    db.add(p)
                    existing.add(email)
                    imported += 1
                    if imported % 500 == 0:
                        await db.flush()
                except Exception as e:
                    errors.append(f"row {idx}: {e}")

        return {"imported": imported, "duplicates_skipped": duplicates_skipped, "errors": errors}

    @mcp.tool()
    async def export_people_csv(
        person_ids: Optional[list[int]] = None,
        client_tag: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> dict[str, Any]:
        """Export people as CSV text. Filter by explicit IDs, client_tag, or industry."""
        import csv, io

        async with db_session() as db:
            q = select(Person)
            if person_ids:
                q = q.where(Person.id.in_(person_ids))
            if client_tag:
                q = q.where(Person.client_tag.ilike(f"%{client_tag}%"))
            if industry:
                q = q.where(Person.industry == industry)
            rows = (await db.execute(q)).scalars().all()

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["First Name", "Last Name", "Email", "Phone", "Company", "Title",
                    "LinkedIn", "Location", "Industry", "Client Tag", "Tags"])
        for p in rows:
            w.writerow([
                p.first_name or "", p.last_name or "", p.email or "", p.phone or "",
                p.company_name or "", p.title or "", p.linkedin_url or "", p.location or "",
                p.industry or "", p.client_tag or "",
                ",".join(p.tags) if p.tags else "",
            ])
        return {"csv": buf.getvalue(), "row_count": len(rows)}

    @mcp.tool()
    async def bulk_enrich_people(person_ids: list[int]) -> dict[str, Any]:
        """Enrich the given people via Apollo.io. Consumes Apollo credits."""
        from app.services.apollo import ApolloService

        if not person_ids:
            return {"enriched_count": 0, "credits_consumed": 0}

        async with db_session() as db:
            rows = (await db.execute(select(Person).where(Person.id.in_(person_ids)))).scalars().all()
            if not rows:
                return {"error": "no_people_found", "person_ids": person_ids}

            apollo = ApolloService()
            enriched = 0
            credits = 0

            for i in range(0, len(rows), 10):
                batch = rows[i:i + 10]
                payload = [{
                    "id": p.id,
                    "first_name": p.first_name,
                    "last_name": p.last_name,
                    "organization_name": p.company_name,
                    "linkedin_url": p.linkedin_url,
                } for p in batch]
                try:
                    result = await apollo.enrich_people(payload)
                    matches = result.get("matches", [])
                    for m in matches:
                        pid = m.get("id")
                        if not pid:
                            continue
                        person = next((p for p in batch if p.id == pid), None)
                        if not person:
                            continue
                        if m.get("email"):
                            person.email = m["email"]
                        nums = m.get("phone_numbers") or []
                        if nums:
                            person.phone = nums[0].get("sanitized_number")
                        person.enriched_at = datetime.now(timezone.utc)
                        enriched += 1
                    credits += len(batch)
                except Exception as e:
                    logger.warning("Apollo batch enrich failed: %s", e)

        return {"enriched_count": enriched, "credits_consumed": credits}

    @mcp.tool()
    async def person_campaigns(person_id: int) -> dict[str, Any]:
        """List the campaigns a person is attached to via their lead list."""
        from app.models.campaign import Campaign
        from app.models.campaign_lead_list import CampaignLeadList

        async with db_session() as db:
            p = await db.get(Person, person_id)
            if not p:
                return {"error": "not_found", "person_id": person_id}
            if not p.list_id:
                return {"campaigns": []}

            res = await db.execute(
                select(Campaign).join(CampaignLeadList, Campaign.id == CampaignLeadList.campaign_id)
                .where(CampaignLeadList.lead_list_id == p.list_id, Campaign.deleted_at.is_(None))
            )
            campaigns = [{
                "id": c.id, "name": c.name,
                "status": c.status.value if hasattr(c.status, "value") else c.status,
                "total_sent": c.total_sent, "total_opened": c.total_opened, "total_replied": c.total_replied,
            } for c in res.scalars().all()]
        return {"campaigns": campaigns}
