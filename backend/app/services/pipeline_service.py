"""Service layer for the waterfall pipeline."""
import math
import uuid
import logging
from typing import Optional

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_run import PipelineRun
from app.models.pipeline_lead import PipelineLead
from app.models.ai_agent import AIAgent

logger = logging.getLogger(__name__)


class PipelineService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_run(
        self,
        ai_agent_id: int,
        client_tag: str,
        icp_override: Optional[dict] = None,
    ) -> PipelineRun:
        # Validate agent exists
        result = await self.db.execute(
            select(AIAgent).where(AIAgent.id == ai_agent_id)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError(f"AI Agent {ai_agent_id} not found")

        # Snapshot ICP from agent or use override
        icp_snapshot = icp_override or agent.icp_json or agent.icp_config

        run = PipelineRun(
            run_id=str(uuid.uuid4()),
            client_tag=client_tag,
            ai_agent_id=ai_agent_id,
            icp_snapshot=icp_snapshot,
            status="pending",
        )
        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)
        return run

    async def list_runs(
        self,
        client_tag: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PipelineRun], int]:
        query = select(PipelineRun)
        count_query = select(sa_func.count(PipelineRun.id))

        if client_tag:
            query = query.where(PipelineRun.client_tag == client_tag)
            count_query = count_query.where(PipelineRun.client_tag == client_tag)
        if status:
            query = query.where(PipelineRun.status == status)
            count_query = count_query.where(PipelineRun.status == status)

        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(PipelineRun.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        runs = list(result.scalars().all())

        return runs, total

    async def get_run(self, run_id: str) -> Optional[PipelineRun]:
        result = await self.db.execute(
            select(PipelineRun).where(PipelineRun.run_id == run_id)
        )
        return result.scalar_one_or_none()

    async def cancel_run(self, run_id: str) -> Optional[PipelineRun]:
        run = await self.get_run(run_id)
        if not run:
            return None
        if run.status in ("completed", "cancelled", "failed"):
            raise ValueError(f"Cannot cancel run with status '{run.status}'")
        run.status = "cancelled"
        await self.db.flush()
        await self.db.refresh(run)
        return run

    async def get_review_queue(
        self,
        client_tag: Optional[str] = None,
        score: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[PipelineLead], int, int]:
        """Returns (leads, total, total_pages)."""
        query = select(PipelineLead).where(
            PipelineLead.pipeline_status.in_(["scored", "review_postponed"])
        )
        count_query = select(sa_func.count(PipelineLead.id)).where(
            PipelineLead.pipeline_status.in_(["scored", "review_postponed"])
        )

        if client_tag:
            query = query.where(PipelineLead.client_tag == client_tag)
            count_query = count_query.where(PipelineLead.client_tag == client_tag)
        if score:
            query = query.where(PipelineLead.icp_score == score)
            count_query = count_query.where(PipelineLead.icp_score == score)

        total = (await self.db.execute(count_query)).scalar() or 0
        total_pages = max(1, math.ceil(total / page_size))

        offset = (page - 1) * page_size
        # Order: A first, then B, then C; postponed at end
        query = (
            query
            .order_by(
                PipelineLead.pipeline_status.asc(),  # 'review_postponed' after 'scored'
                PipelineLead.icp_score.asc(),  # A, B, C
                PipelineLead.created_at.desc(),
            )
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        leads = list(result.scalars().all())

        return leads, total, total_pages

    async def _get_lead(self, lead_id: int) -> Optional[PipelineLead]:
        result = await self.db.execute(
            select(PipelineLead).where(PipelineLead.id == lead_id)
        )
        return result.scalar_one_or_none()

    async def approve_lead(self, lead_id: int) -> Optional[PipelineLead]:
        lead = await self._get_lead(lead_id)
        if not lead:
            return None
        lead.pipeline_status = "approved"
        await self.db.flush()
        await self.db.refresh(lead)
        return lead

    async def discard_lead(self, lead_id: int, reason: Optional[str] = None) -> Optional[PipelineLead]:
        lead = await self._get_lead(lead_id)
        if not lead:
            return None
        lead.pipeline_status = "discarded_manual"
        lead.exclude_flag = True
        if reason:
            lead.exclude_reason = reason
        await self.db.flush()
        await self.db.refresh(lead)
        return lead

    async def postpone_lead(self, lead_id: int) -> Optional[PipelineLead]:
        lead = await self._get_lead(lead_id)
        if not lead:
            return None
        lead.pipeline_status = "review_postponed"
        await self.db.flush()
        await self.db.refresh(lead)
        return lead

    async def update_first_line(self, lead_id: int, first_line_email: str) -> Optional[PipelineLead]:
        lead = await self._get_lead(lead_id)
        if not lead:
            return None
        lead.first_line_email = first_line_email
        await self.db.flush()
        await self.db.refresh(lead)
        return lead
