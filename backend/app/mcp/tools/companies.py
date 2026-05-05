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

    @mcp.tool()
    async def set_company_custom_field(company_id: int, key: str, value: Optional[str] = None) -> dict[str, Any]:
        """Set or remove a Clay-style custom_fields[key] entry on a company. Pass null/empty value to delete the key."""
        key = (key or "").strip()
        if not key:
            return {"error": "empty_key"}
        async with db_session() as db:
            c = await db.get(Company, company_id)
            if not c:
                return {"error": "not_found", "company_id": company_id}
            cf = dict(c.custom_fields or {})
            if value is None or value == "":
                cf.pop(key, None)
            else:
                cf[key] = value
            c.custom_fields = cf or None
            await db.flush()
            await db.refresh(c)
            return company_to_dict(c)

    @mcp.tool()
    async def list_custom_field_keys() -> dict[str, Any]:
        """Distinct keys present in any company's custom_fields. Used to see which user-defined columns exist."""
        async with db_session() as db:
            rows = (await db.execute(select(Company.custom_fields).where(Company.custom_fields.isnot(None)))).all()
        keys: set[str] = set()
        for row in rows:
            cf = row[0]
            if isinstance(cf, dict):
                keys.update(k for k in cf.keys() if k)
        return {"keys": sorted(keys)}

    @mcp.tool()
    async def find_and_import_decision_makers(
        company_id: int,
        titles: Optional[list[str]] = None,
        seniorities: Optional[list[str]] = None,
        per_page: int = 25,
        client_tag: Optional[str] = None,
    ) -> dict[str, Any]:
        """For a given company, search Apollo for decision makers and import them as Person records linked to the company.

        Defaults target executive roles (CEO/Founder/Director/VP/c_suite). Importing here does NOT enrich emails (no Apollo credit cost) — call bulk_enrich_people afterwards on the new person IDs to reveal contact info.
        """
        from app.services.apollo import ApolloService, ApolloAPIError
        from app.models.person import Person

        async with db_session() as db:
            c = await db.get(Company, company_id)
            if not c:
                return {"error": "not_found", "company_id": company_id}

            apollo = ApolloService()
            try:
                raw = await apollo.search_people(
                    person_titles=titles or ["CEO", "Founder", "Co-Founder", "Owner", "Managing Director", "Director", "VP", "Head"],
                    person_seniorities=seniorities or ["c_suite", "vp", "director", "owner", "founder"],
                    organization_keywords=[c.name],
                    per_page=per_page,
                )
            except ApolloAPIError as e:
                return {"error": "apollo_error", "status_code": e.status_code, "detail": e.detail}

            results = apollo.format_people_results(raw)
            existing_emails = {
                r[0].lower() for r in (await db.execute(select(Person.email))).all() if r[0]
            }

            imported = 0
            skipped = 0
            for r in results:
                email = (r.get("email") or "").strip().lower()
                if not email:
                    skipped += 1
                    continue
                if email in existing_emails:
                    skipped += 1
                    continue
                p = Person(
                    first_name=(r.get("first_name") or "Unknown")[:100],
                    last_name=(r.get("last_name") or "Unknown")[:100],
                    email=email[:255],
                    title=r.get("title"),
                    linkedin_url=r.get("linkedin_url"),
                    company_name=c.name,
                    company_id=c.id,
                    industry=r.get("industry") or c.industry,
                    location=r.get("location") or c.location,
                    client_tag=client_tag or c.client_tag,
                )
                db.add(p)
                existing_emails.add(email)
                imported += 1

            return {
                "company_id": c.id,
                "company_name": c.name,
                "candidates_found": len(results),
                "imported": imported,
                "skipped_no_email_or_dup": skipped,
            }

    @mcp.tool()
    async def push_company_decision_makers_to_campaign(
        company_id: int,
        campaign_id: int,
    ) -> dict[str, Any]:
        """Push every Person linked to a company (its decision makers) into the
        given Instantly campaign as leads. Skips persons without a valid email.
        Returns the count uploaded.
        """
        from app.models.campaign import Campaign
        from app.models.person import Person
        from app.services.instantly import instantly_service, InstantlyAPIError

        async with db_session() as db:
            c = await db.get(Company, company_id)
            if not c:
                return {"error": "company_not_found", "company_id": company_id}
            camp = await db.get(Campaign, campaign_id)
            if not camp:
                return {"error": "campaign_not_found", "campaign_id": campaign_id}
            if not camp.instantly_campaign_id:
                return {"error": "campaign_not_synced"}

            persons = (await db.execute(
                select(Person).where(Person.company_id == company_id, Person.email.isnot(None))
            )).scalars().all()
            if not persons:
                return {"uploaded": 0, "message": "No decision makers with email"}

            leads = [{
                "email": p.email,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "company_name": c.name or "",
                "phone": p.phone or "",
                "custom_variables": {
                    "title": p.title or "",
                    "industry": p.industry or c.industry or "",
                    "linkedin_url": p.linkedin_url or "",
                },
            } for p in persons]

            try:
                result = await instantly_service.add_leads_to_campaign(
                    camp.instantly_campaign_id, leads
                )
            except InstantlyAPIError as e:
                return {"error": "instantly_error", "status_code": e.status_code, "detail": e.detail}

        return {
            "company_id": company_id, "campaign_id": campaign_id,
            "campaign_name": camp.name, "uploaded": len(leads),
            "instantly_result": result,
        }

    @mcp.tool()
    async def enrich_company_emails(company_id: int) -> dict[str, Any]:
        """Trigger the web-scraping enrichment pipeline for a company (extracts general emails / phone from the website)."""
        from app.services.enrichment import CompanyEnrichmentService

        async with db_session() as db:
            c = await db.get(Company, company_id)
            if not c:
                return {"error": "not_found", "company_id": company_id}
            if not c.website:
                return {"error": "no_website"}
            service = CompanyEnrichmentService(db)
            try:
                result = await service.enrich_company(c)
                return {
                    "company_id": c.id,
                    "status": getattr(result, "status", "completed"),
                    "emails_found": getattr(result, "emails_found", 0),
                    "phones_found": getattr(result, "phones_found", 0),
                }
            except Exception as e:
                return {"error": "enrichment_failed", "detail": str(e)}
