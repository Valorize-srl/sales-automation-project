from fastapi import APIRouter

from app.api import chat, icps, leads, campaigns, analytics, responses, admin, people, companies

api_router = APIRouter()

api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(icps.router, prefix="/icps", tags=["icps"])
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
api_router.include_router(people.router, prefix="/people", tags=["people"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(responses.router, prefix="/responses", tags=["responses"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
