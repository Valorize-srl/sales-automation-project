"""
Lead List Service - Manage lead lists, tagging, and bulk operations.

Lead Lists organize people and companies by AI Agent and project.
Supports bulk operations like adding/removing leads, tagging, and export.
"""
import csv
import io
import logging
from typing import Optional

from sqlalchemy import select, func as sa_func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead_list import LeadList
from app.models.person import Person
from app.models.company import Company

logger = logging.getLogger(__name__)


class LeadListService:
    """Service for managing lead lists and bulk operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==============================================================================
    # CRUD Operations
    # ==============================================================================

    async def create_list(
        self,
        ai_agent_id: int,
        name: str,
        description: Optional[str] = None,
        filters_snapshot: Optional[dict] = None,
    ) -> LeadList:
        """
        Create new lead list for AI Agent.

        Args:
            ai_agent_id: Parent AI Agent ID
            name: List name (e.g., "Cliente XYZ - Wine Leads")
            description: Optional description
            filters_snapshot: Optional Apollo filters used to create this list

        Returns:
            Created LeadList instance
        """
        lead_list = LeadList(
            ai_agent_id=ai_agent_id,
            name=name,
            description=description,
            filters_snapshot=filters_snapshot,
        )
        self.db.add(lead_list)
        await self.db.commit()
        await self.db.refresh(lead_list)
        logger.info(f"✅ Created Lead List: {name} for Agent {ai_agent_id}")
        return lead_list

    async def get_list(self, list_id: int) -> Optional[LeadList]:
        """Get lead list by ID with AI Agent relationship."""
        result = await self.db.execute(
            select(LeadList)
            .where(LeadList.id == list_id)
            .options(selectinload(LeadList.ai_agent))
        )
        return result.scalar_one_or_none()

    async def list_all_lists(
        self,
        ai_agent_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[LeadList]:
        """
        List all lead lists with optional filtering.

        Args:
            ai_agent_id: Optional filter by AI Agent
            skip: Offset for pagination
            limit: Results per page

        Returns:
            List of LeadList instances
        """
        query = select(LeadList).offset(skip).limit(limit).order_by(LeadList.created_at.desc())

        if ai_agent_id:
            query = query.where(LeadList.ai_agent_id == ai_agent_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_list(
        self,
        list_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[LeadList]:
        """Update lead list name/description."""
        lead_list = await self.get_list(list_id)
        if not lead_list:
            return None

        if name:
            lead_list.name = name
        if description is not None:  # Allow empty string
            lead_list.description = description

        await self.db.commit()
        await self.db.refresh(lead_list)
        logger.info(f"✏️ Updated Lead List {list_id}")
        return lead_list

    async def delete_list(self, list_id: int) -> bool:
        """Delete lead list (sets list_id to NULL in people/companies)."""
        result = await self.db.execute(
            delete(LeadList).where(LeadList.id == list_id)
        )
        await self.db.commit()
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"🗑️ Deleted Lead List {list_id}")
        return deleted

    # ==============================================================================
    # Lead Management
    # ==============================================================================

    async def add_leads_to_list(
        self,
        list_id: int,
        person_ids: Optional[list[int]] = None,
        company_ids: Optional[list[int]] = None,
    ) -> dict:
        """
        Bulk add leads to list.

        Args:
            list_id: Target list ID
            person_ids: List of person IDs to add
            company_ids: List of company IDs to add

        Returns:
            dict with: people_added, companies_added
        """
        lead_list = await self.get_list(list_id)
        if not lead_list:
            raise ValueError(f"Lead list {list_id} not found")

        people_added = 0
        companies_added = 0

        # Add people to list
        if person_ids:
            await self.db.execute(
                update(Person)
                .where(Person.id.in_(person_ids))
                .values(list_id=list_id)
            )
            people_added = len(person_ids)

        # Add companies to list
        if company_ids:
            await self.db.execute(
                update(Company)
                .where(Company.id.in_(company_ids))
                .values(list_id=list_id)
            )
            companies_added = len(company_ids)

        # Update list counts
        await self._update_list_counts(list_id)
        await self.db.commit()

        logger.info(f"➕ Added {people_added} people, {companies_added} companies to List {list_id}")

        return {
            "people_added": people_added,
            "companies_added": companies_added,
        }

    async def remove_leads_from_list(
        self,
        list_id: int,
        person_ids: Optional[list[int]] = None,
        company_ids: Optional[list[int]] = None,
    ) -> dict:
        """
        Bulk remove leads from list (sets list_id to NULL).

        Args:
            list_id: Source list ID
            person_ids: List of person IDs to remove
            company_ids: List of company IDs to remove

        Returns:
            dict with: people_removed, companies_removed
        """
        people_removed = 0
        companies_removed = 0

        # Remove people from list
        if person_ids:
            await self.db.execute(
                update(Person)
                .where(Person.id.in_(person_ids), Person.list_id == list_id)
                .values(list_id=None)
            )
            people_removed = len(person_ids)

        # Remove companies from list
        if company_ids:
            await self.db.execute(
                update(Company)
                .where(Company.id.in_(company_ids), Company.list_id == list_id)
                .values(list_id=None)
            )
            companies_removed = len(company_ids)

        # Update list counts
        await self._update_list_counts(list_id)
        await self.db.commit()

        logger.info(f"➖ Removed {people_removed} people, {companies_removed} companies from List {list_id}")

        return {
            "people_removed": people_removed,
            "companies_removed": companies_removed,
        }

    async def get_list_leads(
        self,
        list_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> dict:
        """
        Get people and companies in a lead list.

        Args:
            list_id: List ID
            skip: Offset for pagination
            limit: Results per page

        Returns:
            dict with: people, companies, total_people, total_companies
        """
        # Get people
        people_result = await self.db.execute(
            select(Person)
            .where(Person.list_id == list_id)
            .offset(skip)
            .limit(limit)
            .order_by(Person.created_at.desc())
        )
        people = list(people_result.scalars().all())

        # Get companies
        companies_result = await self.db.execute(
            select(Company)
            .where(Company.list_id == list_id)
            .offset(skip)
            .limit(limit)
            .order_by(Company.created_at.desc())
        )
        companies = list(companies_result.scalars().all())

        # Get totals
        total_people_result = await self.db.execute(
            select(sa_func.count(Person.id)).where(Person.list_id == list_id)
        )
        total_people = total_people_result.scalar() or 0

        total_companies_result = await self.db.execute(
            select(sa_func.count(Company.id)).where(Company.list_id == list_id)
        )
        total_companies = total_companies_result.scalar() or 0

        return {
            "people": people,
            "companies": companies,
            "total_people": total_people,
            "total_companies": total_companies,
        }

    async def _update_list_counts(self, list_id: int) -> None:
        """Update cached people_count and companies_count for a list."""
        # Count people
        people_result = await self.db.execute(
            select(sa_func.count(Person.id)).where(Person.list_id == list_id)
        )
        people_count = people_result.scalar() or 0

        # Count companies
        companies_result = await self.db.execute(
            select(sa_func.count(Company.id)).where(Company.list_id == list_id)
        )
        companies_count = companies_result.scalar() or 0

        # Update list
        await self.db.execute(
            update(LeadList)
            .where(LeadList.id == list_id)
            .values(people_count=people_count, companies_count=companies_count)
        )

    # ==============================================================================
    # Bulk Tagging Operations
    # ==============================================================================

    async def bulk_tag_leads(
        self,
        person_ids: Optional[list[int]] = None,
        company_ids: Optional[list[int]] = None,
        tags_to_add: Optional[list[str]] = None,
        tags_to_remove: Optional[list[str]] = None,
    ) -> dict:
        """
        Bulk add/remove tags to leads.

        Args:
            person_ids: List of person IDs
            company_ids: List of company IDs
            tags_to_add: Tags to add
            tags_to_remove: Tags to remove

        Returns:
            dict with: people_tagged, companies_tagged
        """
        people_tagged = 0
        companies_tagged = 0

        # Tag people
        if person_ids:
            result = await self.db.execute(
                select(Person).where(Person.id.in_(person_ids))
            )
            people = list(result.scalars().all())

            for person in people:
                if not person.tags:
                    person.tags = []

                # Add tags
                if tags_to_add:
                    for tag in tags_to_add:
                        if tag not in person.tags:
                            person.tags.append(tag)

                # Remove tags
                if tags_to_remove:
                    person.tags = [t for t in person.tags if t not in tags_to_remove]

            people_tagged = len(people)

        # Tag companies
        if company_ids:
            result = await self.db.execute(
                select(Company).where(Company.id.in_(company_ids))
            )
            companies = list(result.scalars().all())

            for company in companies:
                if not company.tags:
                    company.tags = []

                # Add tags
                if tags_to_add:
                    for tag in tags_to_add:
                        if tag not in company.tags:
                            company.tags.append(tag)

                # Remove tags
                if tags_to_remove:
                    company.tags = [t for t in company.tags if t not in tags_to_remove]

            companies_tagged = len(companies)

        await self.db.commit()

        logger.info(f"🏷️ Tagged {people_tagged} people, {companies_tagged} companies")

        return {
            "people_tagged": people_tagged,
            "companies_tagged": companies_tagged,
        }

    # ==============================================================================
    # Export Operations
    # ==============================================================================

    async def export_list_to_csv(self, list_id: int) -> str:
        """
        Export lead list to CSV string.

        Args:
            list_id: List ID to export

        Returns:
            CSV string with all leads
        """
        leads = await self.get_list_leads(list_id, skip=0, limit=10000)  # Get all

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            "Type", "First Name", "Last Name", "Email", "Phone", "Company",
            "Title", "LinkedIn", "Location", "Industry", "Tags"
        ])

        # Write people
        for person in leads["people"]:
            writer.writerow([
                "Person",
                person.first_name or "",
                person.last_name or "",
                person.email or "",
                person.phone or "",
                person.company_name or "",
                person.title or "",
                person.linkedin_url or "",
                person.location or "",
                person.industry or "",
                ",".join(person.tags) if person.tags else "",
            ])

        # Write companies
        for company in leads["companies"]:
            writer.writerow([
                "Company",
                "",  # No first name for companies
                "",  # No last name for companies
                company.email or "",
                company.phone or "",
                company.name or "",
                "",  # No title for companies
                company.linkedin_url or "",
                company.location or "",
                company.industry or "",
                ",".join(company.tags) if company.tags else "",
            ])

        csv_content = output.getvalue()
        output.close()

        logger.info(f"📄 Exported List {list_id} to CSV ({len(leads['people']) + len(leads['companies'])} rows)")

        return csv_content


# Dependency injection helper
async def get_lead_list_service(db: AsyncSession) -> LeadListService:
    """Dependency injection helper for FastAPI routes."""
    return LeadListService(db)
