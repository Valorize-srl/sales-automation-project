from datetime import datetime

from pydantic import BaseModel


class CompanyCSVMapping(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    industry: str | None = None
    location: str | None = None
    signals: str | None = None
    website: str | None = None


class CompanyCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    industry: str | None = None
    location: str | None = None
    signals: str | None = None
    website: str | None = None


class CompanyResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    email: str | None
    email_domain: str | None
    phone: str | None
    linkedin_url: str | None
    industry: str | None
    location: str | None
    signals: str | None
    website: str | None
    created_at: datetime
    people_count: int = 0


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
