"""Celery tasks for sentiment analysis."""

from app.workers import celery_app


@celery_app.task(name="sentiment.analyze_responses")
def analyze_responses(campaign_id: int):
    """Analyze email responses for a campaign. To be implemented."""
    pass
