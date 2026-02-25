"""AI Agents API - Manage client-specific AI agents for prospecting and auto-reply."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.ai_agent import (
    AIAgentCreate,
    AIAgentUpdate,
    AIAgentResponse,
    AIAgentListResponse,
    AIAgentStatsResponse,
    ApolloSearchRequest,
    ApolloSearchResponse,
    EnrichLeadsRequest,
    EnrichEstimateResponse,
    EnrichLeadsResponse,
    KnowledgeBaseUpload,
    CampaignAssociation,
)
from app.services.ai_agent import AIAgentService

logger = logging.getLogger(__name__)
router = APIRouter()


# ==============================================================================
# CRUD Operations
# ==============================================================================

@router.post("", response_model=AIAgentResponse, status_code=201)
async def create_agent(
    agent_data: AIAgentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create new AI Agent with ICP configuration."""
    service = AIAgentService(db)
    agent = await service.create_agent(
        name=agent_data.name,
        client_tag=agent_data.client_tag,
        icp_config=agent_data.icp_config,
        description=agent_data.description,
        signals_config=agent_data.signals_config,
        apollo_credits_allocated=agent_data.apollo_credits_allocated,
    )
    return agent


@router.get("", response_model=AIAgentListResponse)
async def list_agents(
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List all AI Agents with optional filtering."""
    service = AIAgentService(db)
    agents = await service.list_agents(is_active=is_active, skip=skip, limit=limit)

    # credits_remaining and credits_percentage_used are @property on the model,
    # Pydantic reads them automatically via from_attributes=True
    return AIAgentListResponse(agents=agents, total=len(agents))


@router.get("/{agent_id}", response_model=AIAgentResponse)
async def get_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get AI Agent by ID."""
    service = AIAgentService(db)
    agent = await service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AI Agent {agent_id} not found")

    return agent


@router.put("/{agent_id}", response_model=AIAgentResponse)
async def update_agent(
    agent_id: int,
    agent_data: AIAgentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update AI Agent fields."""
    service = AIAgentService(db)

    # Convert to dict and filter out None values
    updates = agent_data.model_dump(exclude_unset=True)

    agent = await service.update_agent(agent_id, **updates)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AI Agent {agent_id} not found")

    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete AI Agent (cascades to lists, signals, campaign associations)."""
    service = AIAgentService(db)
    deleted = await service.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"AI Agent {agent_id} not found")


# ==============================================================================
# Knowledge Base Management
# ==============================================================================

@router.post("/{agent_id}/knowledge-base", response_model=AIAgentResponse)
async def upload_knowledge_base(
    agent_id: int,
    kb_data: KnowledgeBaseUpload,
    db: AsyncSession = Depends(get_db),
):
    """Upload/update knowledge base for AI Replier."""
    service = AIAgentService(db)

    try:
        agent = await service.upload_knowledge_base(
            agent_id=agent_id,
            source_type=kb_data.source_type,
            content=kb_data.content,
            files_metadata=kb_data.files_metadata,
        )
        return agent
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{agent_id}/knowledge-base/upload-pdf", response_model=AIAgentResponse)
async def upload_pdf_knowledge_base(
    agent_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload PDF file and extract text for knowledge base."""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    service = AIAgentService(db)

    try:
        pdf_content = await file.read()
        agent = await service.extract_pdf_knowledge_base(
            agent_id=agent_id,
            pdf_content=pdf_content,
            filename=file.filename,
        )
        return agent
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract PDF: {str(e)}")


# ==============================================================================
# Apollo Search & Enrichment
# ==============================================================================

@router.post("/{agent_id}/search-apollo", response_model=ApolloSearchResponse)
async def execute_apollo_search(
    agent_id: int,
    search_params: ApolloSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute Apollo search using agent's ICP config."""
    service = AIAgentService(db)

    try:
        result = await service.execute_apollo_search(
            agent_id=agent_id,
            per_page=search_params.per_page,
            auto_create_list=search_params.auto_create_list,
            list_name=search_params.list_name,
        )
        return ApolloSearchResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Apollo search error: {e}")
        raise HTTPException(status_code=500, detail=f"Apollo search failed: {str(e)}")


@router.post("/{agent_id}/estimate-enrich", response_model=EnrichEstimateResponse)
async def estimate_enrich_cost(
    agent_id: int,
    enrich_request: EnrichLeadsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Estimate cost before enrichment operation."""
    service = AIAgentService(db)

    estimate = await service.estimate_enrich_cost(
        person_ids=enrich_request.person_ids,
        company_ids=enrich_request.company_ids,
    )
    return EnrichEstimateResponse(**estimate)


@router.post("/{agent_id}/enrich-leads", response_model=EnrichLeadsResponse)
async def enrich_selected_leads(
    agent_id: int,
    enrich_request: EnrichLeadsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Enrich specific leads (email enrichment via Apollo)."""
    service = AIAgentService(db)

    try:
        result = await service.enrich_selected_leads(
            agent_id=agent_id,
            person_ids=enrich_request.person_ids,
            company_ids=enrich_request.company_ids,
        )
        return EnrichLeadsResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Enrichment error: {e}")
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")


# ==============================================================================
# Stats & Analytics
# ==============================================================================

@router.get("/{agent_id}/stats", response_model=AIAgentStatsResponse)
async def get_agent_stats(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get comprehensive agent statistics."""
    service = AIAgentService(db)

    stats = await service.get_agent_stats(agent_id)
    if not stats:
        raise HTTPException(status_code=404, detail=f"AI Agent {agent_id} not found")

    return AIAgentStatsResponse(**stats)


# ==============================================================================
# Campaign Association for Auto-Reply
# ==============================================================================

@router.get("/{agent_id}/campaigns")
async def get_associated_campaigns(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all campaigns associated with this AI Agent."""
    service = AIAgentService(db)

    campaigns = await service.get_associated_campaigns(agent_id)

    return {
        "campaigns": [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status.value,
                "instantly_campaign_id": c.instantly_campaign_id,
                "total_sent": c.total_sent,
                "total_opened": c.total_opened,
                "total_replied": c.total_replied,
                "created_at": c.created_at.isoformat(),
            }
            for c in campaigns
        ],
        "total": len(campaigns),
    }


@router.post("/{agent_id}/campaigns", status_code=201)
async def associate_campaigns(
    agent_id: int,
    association: CampaignAssociation,
    db: AsyncSession = Depends(get_db),
):
    """Associate AI Agent with campaigns for auto-reply."""
    service = AIAgentService(db)

    try:
        result = await service.associate_campaigns(
            agent_id=agent_id,
            campaign_ids=association.campaign_ids
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{agent_id}/campaigns/{campaign_id}", status_code=204)
async def disassociate_campaign(
    agent_id: int,
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Disconnect campaign from AI Agent."""
    service = AIAgentService(db)

    deleted = await service.disassociate_campaign(
        agent_id=agent_id,
        campaign_id=campaign_id
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"No association found between AI Agent {agent_id} and Campaign {campaign_id}"
        )
