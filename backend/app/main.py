import logging
import sys

from fastapi import FastAPI

# Force logs to stdout so Railway can capture them
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting app module import...")

app = FastAPI(title="Sales Automation API", version="0.1.0")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.on_event("startup")
async def startup():
    logger.info("FastAPI startup complete")
