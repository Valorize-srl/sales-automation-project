"""Website scraper API — extract emails and LinkedIn company URL from one or more websites."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl, field_validator

from app.services.website_scraper import scrape_website, scrape_websites_bulk

logger = logging.getLogger(__name__)
router = APIRouter()


class ScrapeRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        return v


class ScrapeBulkRequest(BaseModel):
    urls: list[str]
    concurrency: int = 5

    @field_validator("urls")
    @classmethod
    def normalize_urls(cls, v: list[str]) -> list[str]:
        out = []
        for url in v:
            url = url.strip()
            if url and not url.startswith(("http://", "https://")):
                url = "https://" + url
            if url:
                out.append(url)
        return out[:100]  # hard cap


class ScrapeResult(BaseModel):
    url: str
    emails: list[str]
    linkedin_url: Optional[str]
    pages_visited: int
    error: Optional[str]


@router.post("/scrape", response_model=ScrapeResult)
async def scrape_single(body: ScrapeRequest):
    """Scrape a single website and return found emails and LinkedIn company page URL."""
    result = await scrape_website(body.url)
    return ScrapeResult(**result)


@router.post("/scrape-bulk", response_model=list[ScrapeResult])
async def scrape_bulk(body: ScrapeBulkRequest):
    """Scrape up to 100 websites concurrently and return contacts for each."""
    if not body.urls:
        raise HTTPException(status_code=422, detail="urls list is empty")
    results = await scrape_websites_bulk(body.urls, concurrency=body.concurrency)
    return [ScrapeResult(**r) for r in results]
