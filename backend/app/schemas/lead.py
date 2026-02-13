from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LeadCreate(BaseModel):
    icp_id: int
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=1, max_length=255)
    company: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None


class LeadResponse(BaseModel):
    id: int
    icp_id: int
    first_name: str
    last_name: str
    email: str
    company: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    source: str
    verified: bool
    score: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    leads: list[LeadResponse]
    total: int


class CSVColumnMapping(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None


class CSVUploadResponse(BaseModel):
    headers: list[str]
    mapping: CSVColumnMapping
    rows: list[dict]
    preview_rows: list[dict]
    total_rows: int


class CSVImportRequest(BaseModel):
    icp_id: int
    mapping: CSVColumnMapping
    rows: list[dict]


class CSVImportResponse(BaseModel):
    imported: int
    duplicates_skipped: int
    errors: int
