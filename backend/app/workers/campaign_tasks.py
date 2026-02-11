"""Celery tasks for campaign management."""

from app.workers import celery_app


@celery_app.task(name="campaigns.sync_campaign")
def sync_campaign(campaign_id: int):
    """Sync campaign data with Instantly. To be implemented."""
    pass
