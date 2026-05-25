from fastapi import APIRouter

from app.api import (
    campaigns,
    analytics,
    responses,
    admin,
    people,
    companies,
    usage,
    settings,
    lead_lists,
    tools,
    api_keys,
    activity,
    scraper,
    webhooks,
)

api_router = APIRouter()

api_router.include_router(lead_lists.router, prefix="/lead-lists", tags=["lead-lists"])
api_router.include_router(people.router, prefix="/people", tags=["people"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(responses.router, prefix="/responses", tags=["responses"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(api_keys.router, prefix="/admin/api-keys", tags=["admin"])
api_router.include_router(activity.router, prefix="/activity", tags=["activity"])
api_router.include_router(scraper.router, prefix="/scraper", tags=["scraper"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
