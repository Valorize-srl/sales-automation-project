"""Celery tasks for the waterfall lead generation pipeline."""
import logging

from app.workers import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="pipeline.run_pipeline", bind=True)
def run_pipeline_task(self, run_id: int):
    """
    Main pipeline orchestrator task.

    Phase 1: Placeholder — updates run status to 'running' then 'completed'.
    Phase 2+: Will call each step function sequentially.
    """
    logger.info(f"Pipeline task started for run_id={run_id}")
    # TODO Phase 2: implement actual pipeline execution
    # _step_1_scrape_portals(run_id)
    # _step_2_filter_icp(run_id)
    # ...


# === Step function skeletons (Phase 2+) ===

def _step_1_scrape_portals(run_id: int):
    """Step 1: Scrape Italian business portals."""
    pass


def _step_2_filter_icp(run_id: int):
    """Step 2: Filter raw leads against ICP criteria."""
    pass


def _step_3_linkedin_company(run_id: int):
    """Step 3: Find LinkedIn company profiles."""
    pass


def _step_4_find_dm(run_id: int):
    """Step 4: Find decision makers via LinkedIn."""
    pass


def _step_5_find_emails(run_id: int):
    """Step 5: Email finding waterfall (website scraper → Hunter → Apollo → fallback)."""
    pass


def _step_6_verify_emails(run_id: int):
    """Step 6: Verify emails via ZeroBounce."""
    pass


def _step_7_collect_signals(run_id: int):
    """Step 7: Collect signals (LinkedIn posts, job openings, web mentions)."""
    pass


def _step_8_score_claude(run_id: int):
    """Step 8: Score leads with Claude AI + generate first line email."""
    pass


def _step_9_push_instantly(run_id: int):
    """Step 9: Push approved leads to Instantly campaigns."""
    pass
