from datetime import datetime

from pydantic import BaseModel


class PersonCSVMapping(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    company_name: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None
    industry: str | None = None
    location: str | None = None


class PersonCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    company_name: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None
    industry: str | None = None
    location: str | None = None


class PersonResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    first_name: str
    last_name: str
    company_id: int | None
    company_name: str | None
    email: str
    linkedin_url: str | None
    phone: str | None
    industry: str | None
    location: str | None
    created_at: datetime


class PersonListResponse(BaseModel):
    people: list[PersonResponse]
    total: int


class PersonCSVUploadResponse(BaseModel):
    headers: list[str]
    mapping: PersonCSVMapping
    rows: list[dict]
    preview_rows: list[dict]
    total_rows: int
    unmapped_headers: list[str]


class PersonCSVImportRequest(BaseModel):
    mapping: PersonCSVMapping
    rows: list[dict]


class PersonCSVImportResponse(BaseModel):
    imported: int
    duplicates_skipped: int
    errors: int
