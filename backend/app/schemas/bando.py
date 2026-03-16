"""Schemas for Bandi Monitor API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BandoOut(BaseModel):
    id: int
    source: str
    source_url: str
    title: str
    raw_description: Optional[str] = None
    published_at: Optional[datetime] = None
    status: str
    ai_summary: Optional[str] = None
    target_companies: Optional[str] = None
    ateco_codes: Optional[list[str]] = None
    deadline: Optional[datetime] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    funding_type: Optional[str] = None
    regions: Optional[list[str]] = None
    sectors: Optional[list[str]] = None
    fetched_at: datetime
    analyzed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BandoListResponse(BaseModel):
    bandi: list[BandoOut]
    total: int


class BandoStatsOut(BaseModel):
    total: int
    new_count: int
    analyzed_count: int
    expiring_soon: int
    sources_breakdown: dict[str, int]


class FetchBandiResponse(BaseModel):
    fetched: int
    analyzed: int
    errors: int
    message: str
