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
    # Enrichment fields
    generic_emails: Optional[list[str]] = None
    enrichment_source: Optional[str] = None
    enrichment_date: Optional[datetime] = None
    enrichment_status: Optional[str] = None
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


class CompanyCSVImportResponse(BaseModel):
    imported: int
    duplicates_skipped: int
    errors: int
