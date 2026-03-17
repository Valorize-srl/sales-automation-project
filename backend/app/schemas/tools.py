"""Pydantic schemas for direct tool API endpoints."""

from typing import Optional
from pydantic import BaseModel, Field


# ── Request Models ──────────────────────────────────────────────────

class ApolloSearchPeopleRequest(BaseModel):
    person_titles: Optional[list[str]] = None
    person_locations: Optional[list[str]] = None
    person_seniorities: Optional[list[str]] = None
    organization_keywords: Optional[list[str]] = None
    organization_sizes: Optional[list[str]] = None
    keywords: Optional[str] = None
    per_page: int = Field(default=25, ge=1, le=100)
    client_tag: Optional[str] = None


class ApolloSearchCompaniesRequest(BaseModel):
    organization_locations: Optional[list[str]] = None
    organization_keywords: Optional[list[str]] = None
    organization_sizes: Optional[list[str]] = None
    technologies: Optional[list[str]] = None
    keywords: Optional[str] = None
    per_page: int = Field(default=25, ge=1, le=100)
    client_tag: Optional[str] = None


class ApolloEnrichRequest(BaseModel):
    person_ids: list[int] = Field(..., description="IDs of Person records to enrich")
    client_tag: Optional[str] = None


class GoogleMapsSearchRequest(BaseModel):
    query: str
    location: Optional[str] = None
    max_results: int = Field(default=20, ge=1, le=100)
    client_tag: Optional[str] = None


class ScrapeWebsitesRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, max_length=50)
    client_tag: Optional[str] = None


class ImportLeadsRequest(BaseModel):
    results: list[dict]
    import_type: str = Field(default="people", pattern="^(people|companies)$")
    client_tag: Optional[str] = None
    list_id: Optional[int] = None


class LinkedInSearchPeopleRequest(BaseModel):
    keywords: str = Field(..., description="Job title or role, e.g. 'CEO', 'Sales Director'")
    company: Optional[str] = None
    location: Optional[str] = None
    max_results: int = Field(default=10, ge=1, le=25)
    client_tag: Optional[str] = None


class LinkedInSearchCompaniesRequest(BaseModel):
    company_urls: Optional[list[str]] = None
    company_names: Optional[list[str]] = None
    client_tag: Optional[str] = None


class GenerateCsvRequest(BaseModel):
    results: list[dict]
    columns: Optional[list[str]] = None
    filename: Optional[str] = None


# ── Response Models ─────────────────────────────────────────────────

class ToolSearchResponse(BaseModel):
    results: list[dict]
    total: int
    credits_used: int = 0
    cost_usd: float = 0.0


class ImportLeadsResponse(BaseModel):
    imported: int
    skipped: int
    errors: int = 0
    message: str


class ApolloEnrichResponse(BaseModel):
    enriched: int
    total_requested: int
    credits_used: int = 0
    cost_usd: float = 0.0
    message: str
