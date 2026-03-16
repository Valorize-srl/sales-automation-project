"""Celery tasks for bandi monitoring — fetch and analyze government grants."""

from app.workers import celery_app


@celery_app.task(name="bandi.fetch_and_analyze")
def fetch_and_analyze():
    """Fetch new bandi from all sources and analyze them with AI."""
    # Lazy imports to prevent API startup crash
    import asyncio
    asyncio.run(_fetch_and_analyze())


async def _fetch_and_analyze():
    from app.db.database import async_session_factory
    from app.services.bandi_monitor import BandiMonitorService

    async with async_session_factory() as db:
        service = BandiMonitorService(db)

        # Step 1: Fetch from all sources
        fetch_result = await service.fetch_all_sources()

        # Step 2: Analyze new bandi with AI
        analyzed = await service.analyze_new_bandi()

        return {
            "fetched": fetch_result["fetched"],
            "analyzed": analyzed,
            "errors": fetch_result["errors"],
        }
