import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://www.miriade.ai",
    "https://miriade.ai",
    "https://sales-automation-project.up.railway.app",
    "https://sales-automation-project-production.up.railway.app",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    yield


app = FastAPI(
    title="Sales Automation API",
    description="B2B outreach automation platform with AI-powered ICP parsing and campaign management",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler ensures CORS headers are present even on unhandled 500 errors."""
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    origin = request.headers.get("origin", "")
    headers = {}
    if origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
        headers=headers,
    )


app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway and monitoring."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.app_env,
    }


@app.get("/debug/db-test")
async def debug_db_test():
    """Temporary debug endpoint to test database connectivity."""
    from app.db.database import async_session_factory
    from sqlalchemy import text
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            val = result.scalar()
            # Check what tables exist
            tables_result = await session.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            )
            tables = [row[0] for row in tables_result.all()]
            # Check alembic version
            try:
                version_result = await session.execute(text("SELECT version_num FROM alembic_version"))
                version = version_result.scalar()
            except Exception:
                version = "alembic_version table not found"
            return {
                "db_connected": True,
                "test_query": val,
                "tables": tables,
                "alembic_version": version,
            }
    except Exception as e:
        return {"db_connected": False, "error": f"{type(e).__name__}: {e}"}
