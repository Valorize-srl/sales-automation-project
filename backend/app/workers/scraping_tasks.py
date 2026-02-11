"""Celery tasks for lead scraping operations."""

from app.workers import celery_app


@celery_app.task(name="scraping.scrape_leads")
def scrape_leads(icp_id: int):
    """Scrape leads for a given ICP. To be implemented."""
    pass
