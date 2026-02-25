"""
AI Agent Service - Manage client-specific AI agents for prospecting and auto-reply.

Each AI Agent represents a client configuration with:
- ICP (Ideal Customer Profile) for lead targeting
- Signals configuration (LinkedIn keywords, company triggers)
- Knowledge base for AI-generated email replies
- Budget tracking (Apollo credits allocation/consumption)
"""
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, func as sa_func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_agent import AIAgent
from app.models.ai_agent_campaign import AIAgentCampaign
from app.models.campaign import Campaign
from app.models.lead_list import LeadList
from app.models.person import Person
from app.models.company import Company
from app.models.apollo_search_history import ApolloSearchHistory
from app.services.apollo import ApolloService

logger = logging.getLogger(__name__)


class AIAgentService:
    """Service for managing AI Agents and their operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.apollo = ApolloService()

    # ==============================================================================
    # CRUD Operations
    # ==============================================================================

    async def create_agent(
        self,
        name: str,
        client_tag: str,
        icp_config: dict,
        description: Optional[str] = None,
        signals_config: Optional[dict] = None,
        apollo_credits_allocated: int = 1000,
    ) -> AIAgent:
        """
        Create new AI Agent with ICP configuration.

        Args:
            name: Agent display name (e.g., "Cliente XYZ Wine Prospecting")
            client_tag: Unique tag for lead tagging (e.g., "cliente_xyz")
            icp_config: ICP configuration dict (industry, size, titles, etc.)
            description: Optional detailed description
            signals_config: Optional signals tracking configuration
            apollo_credits_allocated: Monthly Apollo credits budget

        Returns:
            Created AIAgent instance
        """
        agent = AIAgent(
            name=name,
            client_tag=client_tag,
            icp_config=icp_config,
            description=description,
            signals_config=signals_config,
            apollo_credits_allocated=apollo_credits_allocated,
        )
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        logger.info(f"✅ Created AI Agent: {name} (tag: {client_tag})")
        return agent

    async def get_agent(self, agent_id: int) -> Optional[AIAgent]:
        """Get AI Agent by ID with relationships."""
        result = await self.db.execute(
            select(AIAgent)
            .where(AIAgent.id == agent_id)
            .options(selectinload(AIAgent.lead_lists))
        )
        return result.scalar_one_or_none()

    async def get_agent_by_tag(self, client_tag: str) -> Optional[AIAgent]:
        """Get AI Agent by client tag."""
        result = await self.db.execute(
            select(AIAgent).where(AIAgent.client_tag == client_tag)
        )
        return result.scalar_one_or_none()

    async def list_agents(
        self,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AIAgent]:
        """List all AI Agents with optional filtering."""
        query = select(AIAgent).offset(skip).limit(limit).order_by(AIAgent.created_at.desc())

        if is_active is not None:
            query = query.where(AIAgent.is_active == is_active)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_agent(
        self,
        agent_id: int,
        **updates: Any
    ) -> Optional[AIAgent]:
        """
        Update AI Agent fields.

        Args:
            agent_id: Agent ID to update
            **updates: Fields to update (name, icp_config, signals_config, etc.)

        Returns:
            Updated AIAgent or None if not found
        """
        agent = await self.get_agent(agent_id)
        if not agent:
            return None

        for key, value in updates.items():
            if hasattr(agent, key) and value is not None:
                setattr(agent, key, value)

        agent.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(agent)
        logger.info(f"✏️ Updated AI Agent {agent_id}: {list(updates.keys())}")
        return agent

    async def delete_agent(self, agent_id: int) -> bool:
        """Delete AI Agent (cascades to lists, signals, campaign associations)."""
        result = await self.db.execute(
            delete(AIAgent).where(AIAgent.id == agent_id)
        )
        await self.db.commit()
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"🗑️ Deleted AI Agent {agent_id}")
        return deleted

    # ==============================================================================
    # Knowledge Base Management
    # ==============================================================================

    async def upload_knowledge_base(
        self,
        agent_id: int,
        source_type: str,  # "upload" | "url" | "manual"
        content: str,
        files_metadata: Optional[list[dict]] = None,
    ) -> AIAgent:
        """
        Upload/update knowledge base for AI Replier.

        Args:
            agent_id: Agent ID
            source_type: "upload" (PDF/doc files), "url" (website), or "manual" (text)
            content: Extracted text content
            files_metadata: Optional list of file metadata dicts

        Returns:
            Updated AIAgent
        """
        agent = await self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        agent.knowledge_base_text = content
        agent.knowledge_base_source = source_type

        if files_metadata:
            agent.knowledge_base_files = files_metadata

        agent.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(agent)

        logger.info(f"📚 Updated knowledge base for Agent {agent_id} ({source_type})")
        return agent

    # ==============================================================================
    # Apollo Search Integration
    # ==============================================================================

    async def execute_apollo_search(
        self,
        agent_id: int,
        per_page: int = 100,
        auto_create_list: bool = True,
        list_name: Optional[str] = None,
        auto_enrich: bool = True,
    ) -> dict:
        """
        Execute Apollo search using agent's ICP config.

        Flow:
        1. Build Apollo filters from icp_config
        2. Call Apollo search API
        3. Auto-create LeadList (if enabled)
        4. Import results to Person/Company with tags
        5. Update agent credits consumed
        6. Return results summary

        Args:
            agent_id: Agent ID
            per_page: Results per page (max 100)
            auto_create_list: Auto-create lead list for results
            list_name: Optional custom list name

        Returns:
            dict with: list_id, results_count, people_count, companies_count, credits_consumed
        """
        agent = await self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        icp = agent.icp_config
        logger.info(f"🔍 Executing Apollo search for Agent {agent.name} with ICP: {icp}")

        # Build Apollo search filters from ICP
        search_filters = self._build_apollo_filters_from_icp(icp)

        # Execute search
        apollo_result = await self.apollo.search_people(
            person_titles=search_filters.get("person_titles"),
            person_locations=search_filters.get("person_locations"),
            person_seniorities=search_filters.get("person_seniorities"),
            organization_keywords=search_filters.get("organization_keywords"),
            organization_sizes=search_filters.get("organization_sizes"),
            keywords=search_filters.get("keywords"),
            per_page=per_page,
            auto_enrich=auto_enrich,
        )

        people = apollo_result.get("people", [])
        breadcrumbs = apollo_result.get("breadcrumbs", {})

        # Use actual credits consumed from Apollo response
        credits_consumed = apollo_result.get("credits_consumed", 0)

        # Update agent credits
        agent.apollo_credits_consumed += credits_consumed
        await self.db.commit()

        # Create lead list if enabled
        lead_list = None
        if auto_create_list:
            if not list_name:
                list_name = f"{agent.name} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

            lead_list = LeadList(
                ai_agent_id=agent.id,
                name=list_name,
                filters_snapshot=search_filters,
            )
            self.db.add(lead_list)
            await self.db.commit()
            await self.db.refresh(lead_list)

        # Import people to database
        imported_people = await self._import_apollo_people_to_db(
            people=people,
            agent=agent,
            lead_list=lead_list,
        )

        # Update list counts
        if lead_list:
            lead_list.people_count = len(imported_people)
            await self.db.commit()

        # Save search history
        search_history = ApolloSearchHistory(
            search_type="people",
            filters=search_filters,
            results_count=len(people),
            total_results=breadcrumbs.get("total_results", len(people)),
            credits_consumed=credits_consumed,
            client_tag=agent.client_tag,
        )
        self.db.add(search_history)
        await self.db.commit()

        logger.info(f"✅ Apollo search complete: {len(imported_people)} people imported, {credits_consumed} credits used")

        return {
            "list_id": lead_list.id if lead_list else None,
            "list_name": list_name if lead_list else None,
            "results_count": len(people),
            "people_count": len(imported_people),
            "companies_count": 0,  # TODO: Extract companies from people
            "credits_consumed": credits_consumed,
            "credits_remaining": agent.credits_remaining,
        }

    def _build_apollo_filters_from_icp(self, icp: dict) -> dict:
        """Build Apollo API filters from ICP configuration."""
        filters = {}

        # Job titles
        if icp.get("job_titles"):
            titles = [t.strip() for t in icp["job_titles"].split(",") if t.strip()]
            filters["person_titles"] = titles

        # Locations/Geography
        if icp.get("geography"):
            locations = [l.strip() for l in icp["geography"].split(",") if l.strip()]
            filters["person_locations"] = locations
        elif icp.get("location"):
            locations = [l.strip() for l in icp["location"].split(",") if l.strip()]
            filters["person_locations"] = locations

        # Industry/Keywords
        if icp.get("industry"):
            keywords = [icp["industry"]]
            if icp.get("keywords"):
                keywords.extend([k.strip() for k in icp["keywords"].split(",") if k.strip()])
            filters["organization_keywords"] = keywords

        # Company size
        if icp.get("company_size"):
            filters["organization_sizes"] = [icp["company_size"]]

        # Seniority (if available in ICP)
        if icp.get("seniority"):
            seniorities = [s.strip() for s in icp["seniority"].split(",") if s.strip()]
            filters["person_seniorities"] = seniorities

        # General keywords
        if icp.get("keywords") and not icp.get("industry"):
            filters["keywords"] = icp["keywords"]

        return filters

    async def _import_apollo_people_to_db(
        self,
        people: list[dict],
        agent: AIAgent,
        lead_list: Optional[LeadList] = None,
    ) -> list[Person]:
        """Import Apollo search results into Person table with agent tagging."""
        imported = []

        for person_data in people:
            # Check if person already exists by email or LinkedIn
            existing = None
            if person_data.get("email"):
                result = await self.db.execute(
                    select(Person).where(Person.email == person_data["email"])
                )
                existing = result.scalar_one_or_none()

            if not existing and person_data.get("linkedin_url"):
                result = await self.db.execute(
                    select(Person).where(Person.linkedin_url == person_data["linkedin_url"])
                )
                existing = result.scalar_one_or_none()

            if existing:
                # Update existing person: add tags, list_id, enrich data
                if not existing.tags:
                    existing.tags = []
                if agent.client_tag not in existing.tags:
                    existing.tags.append(agent.client_tag)

                if lead_list:
                    existing.list_id = lead_list.id

                # Update enrichment data
                if person_data.get("email"):
                    existing.email = person_data["email"]
                if person_data.get("phone"):
                    existing.phone = person_data["phone"]
                if person_data.get("title"):
                    existing.title = person_data["title"]

                existing.enriched_at = datetime.utcnow()
                imported.append(existing)
            else:
                # Create new person
                org = person_data.get("organization", {})

                new_person = Person(
                    first_name=person_data.get("first_name"),
                    last_name=person_data.get("last_name"),
                    email=person_data.get("email"),
                    phone=person_data.get("phone"),
                    title=person_data.get("title"),
                    linkedin_url=person_data.get("linkedin_url"),
                    company_name=org.get("name"),
                    location=person_data.get("city") or person_data.get("state"),
                    industry=org.get("industry"),
                    tags=[agent.client_tag],
                    list_id=lead_list.id if lead_list else None,
                    client_tag=agent.client_tag,
                    enriched_at=datetime.utcnow(),
                )
                self.db.add(new_person)
                imported.append(new_person)

        await self.db.commit()
        return imported

    # ==============================================================================
    # Enrichment & Cost Estimation
    # ==============================================================================

    async def estimate_enrich_cost(
        self,
        person_ids: Optional[list[int]] = None,
        company_ids: Optional[list[int]] = None,
    ) -> dict:
        """
        Calculate cost estimate before enrichment operation.

        Args:
            person_ids: List of person IDs to enrich
            company_ids: List of company IDs to enrich

        Returns:
            dict with: total_leads, apollo_credits_needed, estimated_cost_usd
        """
        total_leads = 0

        if person_ids:
            total_leads += len(person_ids)

        if company_ids:
            total_leads += len(company_ids)

        # Apollo enrichment cost: 1 credit per person/company
        apollo_credits_needed = total_leads
        estimated_cost_usd = apollo_credits_needed * 0.10  # $0.10 per credit

        return {
            "total_leads": total_leads,
            "apollo_credits_needed": apollo_credits_needed,
            "estimated_cost_usd": round(estimated_cost_usd, 2),
        }

    async def enrich_selected_leads(
        self,
        agent_id: int,
        person_ids: Optional[list[int]] = None,
        company_ids: Optional[list[int]] = None,
    ) -> dict:
        """
        Enrich specific leads (email enrichment via Apollo).

        Args:
            agent_id: Agent ID for credit tracking
            person_ids: List of person IDs to enrich
            company_ids: List of company IDs to enrich

        Returns:
            dict with: enriched_count, credits_consumed, credits_remaining
        """
        agent = await self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        enriched_count = 0
        credits_consumed = 0

        # Enrich people
        if person_ids:
            # Fetch people from DB
            result = await self.db.execute(
                select(Person).where(Person.id.in_(person_ids))
            )
            people = list(result.scalars().all())

            # Batch enrich in groups of 10 (Apollo API limit)
            for i in range(0, len(people), 10):
                batch = people[i:i+10]

                # Prepare data for Apollo
                apollo_people = [
                    {
                        "id": p.id,
                        "first_name": p.first_name,
                        "last_name": p.last_name,
                        "organization_name": p.company_name,
                        "linkedin_url": p.linkedin_url,
                    }
                    for p in batch
                ]

                # Call Apollo enrich API
                try:
                    enrich_result = await self.apollo.enrich_people(apollo_people)
                    matches = enrich_result.get("matches", [])

                    # Update people with enriched data
                    for match in matches:
                        person_id = match.get("id")
                        if person_id:
                            person = next((p for p in batch if p.id == person_id), None)
                            if person:
                                if match.get("email"):
                                    person.email = match["email"]
                                if match.get("phone_numbers"):
                                    person.phone = match["phone_numbers"][0].get("sanitized_number")
                                person.enriched_at = datetime.utcnow()
                                enriched_count += 1

                    credits_consumed += len(batch)
                except Exception as e:
                    logger.error(f"Apollo enrich error: {e}")

        # TODO: Enrich companies (if company enrichment is needed)

        # Update agent credits
        agent.apollo_credits_consumed += credits_consumed
        await self.db.commit()

        logger.info(f"💎 Enriched {enriched_count} leads, consumed {credits_consumed} credits")

        return {
            "enriched_count": enriched_count,
            "credits_consumed": credits_consumed,
            "credits_remaining": agent.credits_remaining,
        }

    # ==============================================================================
    # Stats & Analytics
    # ==============================================================================

    async def get_agent_stats(self, agent_id: int) -> dict:
        """
        Get comprehensive agent statistics.

        Returns:
            dict with: total_leads, apollo_credits_consumed, apollo_credits_remaining,
                       lists_created, campaigns_connected, signals_detected
        """
        agent = await self.get_agent(agent_id)
        if not agent:
            return {}

        # Count leads with this agent's tag
        people_result = await self.db.execute(
            select(sa_func.count(Person.id)).where(
                Person.tags.contains([agent.client_tag])
            )
        )
        total_people = people_result.scalar() or 0

        companies_result = await self.db.execute(
            select(sa_func.count(Company.id)).where(
                Company.tags.contains([agent.client_tag])
            )
        )
        total_companies = companies_result.scalar() or 0

        # Count lead lists
        lists_result = await self.db.execute(
            select(sa_func.count(LeadList.id)).where(LeadList.ai_agent_id == agent_id)
        )
        lists_created = lists_result.scalar() or 0

        # Count campaigns
        campaigns_result = await self.db.execute(
            select(sa_func.count(AIAgentCampaign.id)).where(
                AIAgentCampaign.ai_agent_id == agent_id
            )
        )
        campaigns_connected = campaigns_result.scalar() or 0

        # Count signals (TODO: when SignalTracking is populated)
        signals_detected = 0

        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "client_tag": agent.client_tag,
            "total_leads": total_people + total_companies,
            "total_people": total_people,
            "total_companies": total_companies,
            "apollo_credits_allocated": agent.apollo_credits_allocated,
            "apollo_credits_consumed": agent.apollo_credits_consumed,
            "apollo_credits_remaining": agent.credits_remaining,
            "apollo_credits_percentage_used": agent.credits_percentage_used,
            "lists_created": lists_created,
            "campaigns_connected": campaigns_connected,
            "signals_detected": signals_detected,
        }

    # ==============================================================================
    # Campaign Association for Auto-Reply
    # ==============================================================================

    async def associate_campaigns(
        self,
        agent_id: int,
        campaign_ids: list[int]
    ) -> dict:
        """
        Associate AI Agent with campaigns for auto-reply functionality.

        Creates AIAgentCampaign records to link the agent with specified campaigns.
        When email responses arrive for these campaigns, the agent's knowledge base
        will be used to generate suggested replies.

        Args:
            agent_id: AI Agent ID
            campaign_ids: List of campaign IDs to associate

        Returns:
            dict with: campaigns_associated, message, details

        Raises:
            ValueError: If agent not found or campaigns not found
        """
        # Validate agent exists
        agent = await self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"AI Agent {agent_id} not found")

        # Validate all campaigns exist
        campaigns_result = await self.db.execute(
            select(Campaign).where(
                Campaign.id.in_(campaign_ids),
                Campaign.deleted_at.is_(None)
            )
        )
        existing_campaigns = list(campaigns_result.scalars().all())

        if len(existing_campaigns) != len(campaign_ids):
            existing_ids = {c.id for c in existing_campaigns}
            missing_ids = set(campaign_ids) - existing_ids
            raise ValueError(f"Campaigns not found: {missing_ids}")

        # Check which campaigns are already associated
        existing_assoc_result = await self.db.execute(
            select(AIAgentCampaign).where(
                AIAgentCampaign.ai_agent_id == agent_id,
                AIAgentCampaign.campaign_id.in_(campaign_ids)
            )
        )
        existing_associations = {assoc.campaign_id for assoc in existing_assoc_result.scalars().all()}

        # Create new associations
        new_associations = []
        for campaign_id in campaign_ids:
            if campaign_id not in existing_associations:
                association = AIAgentCampaign(
                    ai_agent_id=agent_id,
                    campaign_id=campaign_id,
                    auto_reply_enabled=True
                )
                self.db.add(association)
                new_associations.append(campaign_id)

        await self.db.commit()

        logger.info(
            f"🔗 Associated AI Agent {agent_id} ({agent.name}) with {len(new_associations)} new campaigns"
        )

        return {
            "campaigns_associated": len(new_associations),
            "already_associated": len(existing_associations),
            "total_campaigns": len(campaign_ids),
            "message": f"Successfully associated {len(new_associations)} campaigns with AI Agent {agent.name}",
        }

    async def disassociate_campaign(
        self,
        agent_id: int,
        campaign_id: int
    ) -> bool:
        """
        Remove campaign association from AI Agent.

        Deletes the AIAgentCampaign record, disabling auto-reply for this campaign.

        Args:
            agent_id: AI Agent ID
            campaign_id: Campaign ID to disassociate

        Returns:
            True if association was removed, False if it didn't exist
        """
        result = await self.db.execute(
            delete(AIAgentCampaign).where(
                AIAgentCampaign.ai_agent_id == agent_id,
                AIAgentCampaign.campaign_id == campaign_id
            )
        )
        await self.db.commit()

        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"🔓 Disassociated campaign {campaign_id} from AI Agent {agent_id}")

        return deleted

    async def get_associated_campaigns(
        self,
        agent_id: int
    ) -> list[Campaign]:
        """
        Get all campaigns linked to this AI Agent.

        Args:
            agent_id: AI Agent ID

        Returns:
            List of Campaign objects associated with the agent
        """
        result = await self.db.execute(
            select(Campaign)
            .join(AIAgentCampaign, Campaign.id == AIAgentCampaign.campaign_id)
            .where(
                AIAgentCampaign.ai_agent_id == agent_id,
                Campaign.deleted_at.is_(None)
            )
            .order_by(Campaign.created_at.desc())
        )
        return list(result.scalars().all())


# Singleton instance helper
async def get_ai_agent_service(db: AsyncSession) -> AIAgentService:
    """Dependency injection helper for FastAPI routes."""
    return AIAgentService(db)
