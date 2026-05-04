from typing import Optional
from datetime import datetime
import json

from pydantic import BaseModel, field_validator


class CompanyCSVMapping(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    signals: Optional[str] = None
    website: Optional[str] = None


class CompanyCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    signals: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    signals: Optional[str] = None
    website: Optional[str] = None
    client_tag: Optional[str] = None
    notes: Optional[str] = None


class CompanyResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    email: Optional[str]
    email_domain: Optional[str]
    phone: Optional[str]
    linkedin_url: Optional[str]
    industry: Optional[str]
    location: Optional[str]
    signals: Optional[str]
    website: Optional[str]
    client_tag: Optional[str] = None
    notes: Optional[str] = None
    # Enrichment fields
    generic_emails: Optional[list[str]] = None
    enrichment_source: Optional[str] = None
    enrichment_date: Optional[datetime] = None
    enrichment_status: Optional[str] = None
    # ICP scoring fields
    icp_score: Optional[int] = None
    priority_tier: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    revenue_band: Optional[str] = None
    employee_count_band: Optional[str] = None
    industry_standardized: Optional[str] = None
    reason_summary: Optional[str] = None
    last_scored_at: Optional[datetime] = None
    scored_with_icp_id: Optional[int] = None
    created_at: datetime
    people_count: int = 0

    @field_validator('generic_emails', mode='before')
    @classmethod
    def parse_generic_emails(cls, v):
        """Parse generic_emails from JSON string to list."""
        if isinstance(v, str):
            try:
                return json.loads(v) if v else []
            except json.JSONDecodeError:
                return []
        return v or []


class CompanyListResponse(BaseModel):
    companies: list[CompanyResponse]
    total: int
    page: int = 1
    page_size: int = 50
    total_pages: int = 1


class CompanyCSVUploadResponse(BaseModel):
    headers: list[str]
    mapping: CompanyCSVMapping
    rows: list[dict]
    preview_rows: list[dict]
    total_rows: int
    unmapped_headers: list[str]


class CompanyCSVImportRequest(BaseModel):
    mapping: CompanyCSVMapping
    rows: list[dict]
    defaults: Optional[dict[str, str]] = None


class CompanyCSVImportResponse(BaseModel):
    imported: int
    duplicates_skipped: int
    merged: int = 0
    errors: int


class FindPeopleRequest(BaseModel):
    titles: Optional[list[str]] = None
    seniorities: Optional[list[str]] = None
    per_page: int = 25


# ---- Lead Planner & Scorer ----

class CompanyScoreRequest(BaseModel):
    """Trigger ICP scoring on a set of companies (or all if company_ids is null)."""
    icp_id: int
    company_ids: Optional[list[int]] = None


class CompanyScoreResponse(BaseModel):
    icp_id: int
    scored_count: int
    tier_a: int
    tier_b: int
    tier_c: int
    enrichment_tasks_created: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
