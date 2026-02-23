from typing import Optional
from datetime import datetime

from pydantic import BaseModel


class PersonCSVMapping(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None


class PersonCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    company_name: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None


class PersonResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    first_name: str
    last_name: str
    company_id: Optional[int]
    company_name: Optional[str]
    email: str
    linkedin_url: Optional[str]
    phone: Optional[str]
    industry: Optional[str]
    location: Optional[str]
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
