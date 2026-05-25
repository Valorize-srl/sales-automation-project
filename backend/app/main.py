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


async def _ensure_columns():
    """Ensure new columns exist in the database (belt-and-suspenders for migration 021)."""
    from sqlalchemy import text, create_engine
    engine = create_engine(settings.database_url_sync, echo=False)
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE companies ADD COLUMN IF NOT EXISTS notes TEXT",
            "ALTER TABLE people ADD COLUMN IF NOT EXISTS title VARCHAR(255)",
            "ALTER TABLE people ADD COLUMN IF NOT EXISTS notes TEXT",
        ]:
            conn.execute(text(stmt))
        conn.commit()
    engine.dispose()
    logger.info("Startup: ensured DB columns exist")


async def _ensure_indexes():
    """Ensure performance indexes exist (migration 022)."""
    from sqlalchemy import text, create_engine
    engine = create_engine(settings.database_url_sync, echo=False)
    with engine.connect() as conn:
        for stmt in [
            "CREATE INDEX IF NOT EXISTS ix_companies_industry ON companies (industry)",
            "CREATE INDEX IF NOT EXISTS ix_companies_client_tag ON companies (client_tag)",
            "CREATE INDEX IF NOT EXISTS ix_companies_name_lower ON companies (LOWER(name))",
            "CREATE INDEX IF NOT EXISTS ix_people_industry ON people (industry)",
            "CREATE INDEX IF NOT EXISTS ix_people_client_tag ON people (client_tag)",
            "CREATE INDEX IF NOT EXISTS ix_people_email_lower ON people (LOWER(email))",
        ]:
            conn.execute(text(stmt))
        conn.commit()
    engine.dispose()
    logger.info("Startup: ensured DB indexes exist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    try:
        await _ensure_columns()
    except Exception as e:
        logger.error(f"Startup column check failed: {e}")
    try:
        await _ensure_indexes()
    except Exception as e:
        logger.error(f"Startup indexes check failed: {e}")

    # Run the MCP streamable-http app's own lifespan (session manager init) if mounted
    mcp_lifespan = getattr(app.state, "mcp_lifespan", None)
    if mcp_lifespan is not None:
        async with mcp_lifespan(app):
            yield
    else:
        yield


app = FastAPI(
    title="Sales Automation API",
    description="B2B outreach automation platform — companies-first dashboard with Apollo & LinkedIn DM discovery and Instantly campaigns",
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
        content={"detail": "Internal server error"},
        headers=headers,
    )


app.include_router(api_router, prefix="/api")


# Mount MCP (Model Context Protocol) server at /mcp. Protected by API key middleware.
if settings.mcp_enabled:
    try:
        from app.mcp import build_mcp_asgi_app
        mcp_asgi = build_mcp_asgi_app()
        # Forward the MCP session manager lifespan into FastAPI's lifespan above.
        app.state.mcp_lifespan = mcp_asgi.router.lifespan_context
        app.mount("/mcp", mcp_asgi)
        logger.info("MCP server mounted at /mcp")
    except Exception as e:
        logger.error(f"Failed to mount MCP server: {e}", exc_info=True)


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway and monitoring."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.app_env,
    }
