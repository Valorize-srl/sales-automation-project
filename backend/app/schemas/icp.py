from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ICPCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    job_titles: Optional[str] = None
    geography: Optional[str] = None
    revenue_range: Optional[str] = None
    keywords: Optional[str] = None
    raw_input: Optional[str] = None


class ICPUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    job_titles: Optional[str] = None
    geography: Optional[str] = None
    revenue_range: Optional[str] = None
    keywords: Optional[str] = None
    status: Optional[str] = None


class ICPResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    job_titles: Optional[str] = None
    geography: Optional[str] = None
    revenue_range: Optional[str] = None
    keywords: Optional[str] = None
    raw_input: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ICPListResponse(BaseModel):
    icps: list[ICPResponse]
    total: int
