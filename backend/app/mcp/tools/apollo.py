"""MCP tools: Apollo.io prospecting (search, enrich)."""
from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from app.mcp.session import db_session


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def apollo_search_people(
        person_titles: Optional[list[str]] = None,
        person_locations: Optional[list[str]] = None,
        person_seniorities: Optional[list[str]] = None,
        organization_keywords: Optional[list[str]] = None,
        organization_sizes: Optional[list[str]] = None,
        keywords: Optional[str] = None,
        per_page: int = 25,
        auto_enrich: bool = False,
    ) -> dict[str, Any]:
        """Search people on Apollo.io.

        Seniority options: senior, manager, director, vp, c_suite, entry, intern.
        Org size options: 1-10, 11-50, 51-200, 201-500, 501-1000, 1001-5000, 5001+.
        When auto_enrich=True Apollo also reveals emails (1 credit per person).
        """
        from app.services.apollo import ApolloService, ApolloAPIError

        apollo = ApolloService()
        try:
            raw = await apollo.search_people(
                person_titles=person_titles,
                person_locations=person_locations,
                person_seniorities=person_seniorities,
                organization_keywords=organization_keywords,
                organization_sizes=organization_sizes,
                keywords=keywords,
                per_page=per_page,
                auto_enrich=auto_enrich,
            )
        except ApolloAPIError as e:
            return {"error": "apollo_error", "status_code": e.status_code, "detail": e.detail}

        results = apollo.format_people_results(raw)
        pagination = raw.get("pagination", {})
        return {
            "results": results,
            "count": len(results),
            "pagination": {
                "page": pagination.get("page"),
                "per_page": pagination.get("per_page"),
                "total_entries": pagination.get("total_entries"),
                "total_pages": pagination.get("total_pages"),
            },
        }

    @mcp.tool()
    async def apollo_search_organizations(
        keywords: Optional[list[str]] = None,
        locations: Optional[list[str]] = None,
        sizes: Optional[list[str]] = None,
        per_page: int = 25,
    ) -> dict[str, Any]:
        """Search organizations on Apollo.io."""
        from app.services.apollo import ApolloService, ApolloAPIError

        apollo = ApolloService()
        try:
            raw = await apollo.search_organizations(
                keywords=keywords, locations=locations, sizes=sizes, per_page=per_page
            )
        except ApolloAPIError as e:
            return {"error": "apollo_error", "status_code": e.status_code, "detail": e.detail}

        return {"results": apollo.format_org_results(raw), "pagination": raw.get("pagination", {})}

    @mcp.tool()
    async def apollo_credits_status() -> dict[str, Any]:
        """Show remaining Apollo credits on the configured account."""
        from app.services.apollo import ApolloService, ApolloAPIError

        try:
            return await ApolloService().get_credits_status()
        except ApolloAPIError as e:
            return {"error": "apollo_error", "status_code": e.status_code, "detail": e.detail}

    @mcp.tool()
    async def import_apollo_results(
        people: list[dict[str, Any]],
        client_tag: Optional[str] = None,
        default_list_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Persist Apollo search results as Person rows (dedup by email).

        `people` is expected to be the `results` array returned by `apollo_search_people`.
        """
        from sqlalchemy import select
        from app.models.person import Person
        from app.models.company import Company

        imported = 0
        skipped = 0
        errors: list[str] = []

        async with db_session() as db:
            existing_rows = (await db.execute(select(Person.email))).all()
            existing = {r[0].lower() for r in existing_rows if r[0]}

            for idx, p in enumerate(people):
                try:
                    email = (p.get("email") or "").strip().lower()
                    if not email:
                        skipped += 1
                        continue
                    if email in existing:
                        skipped += 1
                        continue

                    company_name = p.get("organization_name") or p.get("company_name")
                    company_id = None
                    if company_name:
                        res = await db.execute(
                            select(Company.id).where(Company.name.ilike(company_name))
                        )
                        company_id = res.scalar_one_or_none()

                    person = Person(
                        first_name=(p.get("first_name") or "Unknown")[:100],
                        last_name=(p.get("last_name") or "Unknown")[:100],
                        email=email[:255],
                        title=p.get("title"),
                        linkedin_url=p.get("linkedin_url"),
                        company_name=company_name,
                        company_id=company_id,
                        industry=p.get("industry"),
                        location=p.get("location"),
                        client_tag=client_tag,
                        list_id=default_list_id,
                    )
                    db.add(person)
                    existing.add(email)
                    imported += 1
                except Exception as e:
                    errors.append(f"row {idx}: {e}")

        return {"imported": imported, "skipped": skipped, "errors": errors}
