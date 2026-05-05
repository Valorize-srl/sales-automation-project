from typing import Optional
from datetime import datetime

from pydantic import BaseModel


class PersonCreate(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    company_name: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    client_tag: Optional[str] = None


class PersonUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    company_name: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    client_tag: Optional[str] = None
    notes: Optional[str] = None
    converted: Optional[bool] = None


class PersonResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    first_name: str
    last_name: str
    company_id: Optional[int]
    company_name: Optional[str]
    email: Optional[str] = None
    linkedin_url: Optional[str]
    phone: Optional[str]
    title: Optional[str] = None
    industry: Optional[str]
    location: Optional[str]
    client_tag: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    converted_at: Optional[datetime] = None
    created_at: datetime


class PersonListResponse(BaseModel):
    people: list[PersonResponse]
    total: int
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
