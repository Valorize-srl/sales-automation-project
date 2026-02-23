"""
Enrichment schemas for company email enrichment API.
"""

from typing import Optional
from pydantic import BaseModel


class EmailFinderResult(BaseModel):
    """Result from email finder service."""
    emails: list[str]
    source_pages: dict[str, str]  # email -> page URL where found
    confidence: dict[str, float]  # email -> confidence score (0.0-1.0)
    error: Optional[str] = None

    class Config:
        from_attributes = True


class EnrichmentResult(BaseModel):
    """Result of enriching a single company."""
    company_id: int
    company_name: str
    status: str  # "completed" | "failed" | "skipped"
    emails_found: list[str]
    error: Optional[str] = None

    class Config:
        from_attributes = True


class CompanyEnrichmentResponse(BaseModel):
    """Response for batch enrichment endpoint."""
    enriched: int
    failed: int
    skipped: int
    results: list[EnrichmentResult]

    class Config:
        from_attributes = True


class EnrichBatchRequest(BaseModel):
    """Request for batch enrichment."""
    company_ids: list[int]
    force: bool = False  # Force re-enrichment even if recently enriched

    class Config:
        from_attributes = True
