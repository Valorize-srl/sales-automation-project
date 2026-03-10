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


async def _ensure_prospecting_tools():
    """Ensure prospecting_tools table exists with seed data (migration 019)."""
    from sqlalchemy import text, create_engine, inspect
    engine = create_engine(settings.database_url_sync, echo=False)
    with engine.connect() as conn:
        inspector = inspect(engine)
        if "prospecting_tools" not in inspector.get_table_names():
            conn.execute(text("""
                CREATE TABLE prospecting_tools (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    display_name VARCHAR(255) NOT NULL,
                    description TEXT,
                    when_to_use TEXT,
                    cost_info VARCHAR(255),
                    sectors_strong JSON,
                    sectors_weak JSON,
                    apify_actor_id VARCHAR(255),
                    output_type VARCHAR(50),
                    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ
                )
            """))
            conn.execute(text("""
                INSERT INTO prospecting_tools (name, display_name, description, when_to_use, cost_info, sectors_strong, sectors_weak, apify_actor_id, output_type, sort_order)
                VALUES
                ('google_maps', 'Google Maps Scraper',
                 'Cerca attivita locali su Google Maps. Ritorna nome, indirizzo, telefono, sito web, rating, categoria.',
                 'Fonte PRIMARIA per trovare aziende. Usa sempre come primo step per qualsiasi settore con presenza fisica locale.',
                 '~$2.10 per 1000 risultati',
                 '["horeca","retail","servizi locali","studi professionali","artigianato","sanita","beauty","automotive"]',
                 '["SaaS","startup tech","enterprise B2B","aziende solo online"]',
                 'compass/crawler-google-places', 'companies', 1),
                ('website_contacts', 'Website Email/Phone Extractor',
                 'Estrae email, telefono e profili social dai siti web trovati.',
                 'Usa DOPO Google Maps o quando hai una lista di URL senza contatti diretti.',
                 '~$0.04 per CU (~gratis)',
                 '["tutti i settori con sito web"]', '["aziende senza sito web"]',
                 'anchor/email-phone-extractor', 'contacts', 2),
                ('linkedin_companies', 'LinkedIn Company Scraper',
                 'Scrapa profili LinkedIn aziendali: descrizione, dipendenti, settore, specialita, follower.',
                 'Usa per arricchire i dati aziendali con info LinkedIn.',
                 '~$0.01 per profilo',
                 '["B2B","tech","servizi professionali","consulting","agenzie digitali"]',
                 '["micro imprese locali","artigiani","attivita senza LinkedIn"]',
                 'curious_coder/linkedin-company-scraper', 'companies', 3),
                ('linkedin_people', 'LinkedIn Profile Search',
                 'Cerca decision maker su LinkedIn per titolo, azienda, zona.',
                 'Usa per trovare i decision maker (CEO, Direttore Commerciale, Marketing Manager, CTO).',
                 '~$0.01 per profilo',
                 '["tutti i settori B2B","management","C-level"]',
                 '["micro imprese senza LinkedIn","settori poco digitalizzati"]',
                 'harvestapi/linkedin-profile-search', 'people', 4)
            """))
            conn.commit()
            logger.info("Startup: created prospecting_tools table with seed data")
        else:
            logger.info("Startup: prospecting_tools table already exists")
    engine.dispose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    try:
        await _ensure_columns()
    except Exception as e:
        logger.error(f"Startup column check failed: {e}")
    try:
        await _ensure_prospecting_tools()
    except Exception as e:
        logger.error(f"Startup prospecting_tools check failed: {e}")
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
        content={"detail": "Internal server error"},
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
