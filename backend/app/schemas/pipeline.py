"""Pydantic schemas for the waterfall pipeline."""
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


# --- ICP JSON Schema ---

class ICPPortaliQuery(BaseModel):
    ateco_whitelist: list[str] = Field(default_factory=list)
    province: list[str] = Field(default_factory=list)
    employees_range: Optional[dict] = None  # {"min": 10, "max": 150}
    revenue_range_eur: Optional[dict] = None  # {"min": 1000000, "max": 20000000}
    legal_form_whitelist: list[str] = Field(default_factory=list)
    company_age_min_years: Optional[int] = None


class ICPJsonSchema(BaseModel):
    client_tag: Optional[str] = None
    knowledge_base_ref: Optional[str] = None
    portali_query: Optional[ICPPortaliQuery] = None
    linkedin_job_titles: list[str] = Field(default_factory=list)
    signals_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    google_maps_categories: list[str] = Field(default_factory=list)


# --- Pipeline Run ---

class PipelineRunCreate(BaseModel):
    ai_agent_id: int
    client_tag: str = Field(..., min_length=1, max_length=100)
    icp_override: Optional[dict] = None


class PipelineRunResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    run_id: str
    client_tag: str
    ai_agent_id: Optional[int] = None
    icp_snapshot: Optional[dict] = None
    status: str
    current_step: int
    leads_raw_count: int
    leads_filtered_count: int
    leads_with_dm_count: int
    leads_with_email_count: int
    leads_verified_count: int
    leads_scored_count: int
    leads_score_a: int
    leads_score_b: int
    leads_score_c: int
    cost_scraping_usd: float
    cost_linkedin_usd: float
    cost_email_finding_usd: float
    cost_zerobounce_usd: float
    cost_signals_usd: float
    cost_claude_usd: float
    cost_total_usd: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class PipelineRunListResponse(BaseModel):
    runs: list[PipelineRunResponse]
    total: int


# --- Pipeline Lead ---

class PipelineLeadResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    pipeline_run_id: int
    ragione_sociale: Optional[str] = None
    partita_iva: Optional[str] = None
    codice_ateco: Optional[str] = None
    forma_giuridica: Optional[str] = None
    fatturato_range: Optional[str] = None
    dipendenti_range: Optional[str] = None
    indirizzo: Optional[str] = None
    provincia: Optional[str] = None
    anno_costituzione: Optional[int] = None
    sito_web: Optional[str] = None
    source_portal: Optional[str] = None
    pipeline_status: str
    linkedin_company_url: Optional[str] = None
    linkedin_industry: Optional[str] = None
    linkedin_employees_count: Optional[int] = None
    linkedin_followers: Optional[int] = None
    linkedin_status: Optional[str] = None
    dm_first_name: Optional[str] = None
    dm_last_name: Optional[str] = None
    dm_job_title: Optional[str] = None
    dm_linkedin_url: Optional[str] = None
    dm_headline: Optional[str] = None
    dm_found: Optional[bool] = None
    email: Optional[str] = None
    email_type: Optional[str] = None
    email_confidence: Optional[float] = None
    email_source: Optional[str] = None
    email_catchall: Optional[bool] = None
    email_unknown: Optional[bool] = None
    signals_json: Optional[dict] = None
    icp_score: Optional[str] = None
    score_reason: Optional[str] = None
    approach_angle: Optional[str] = None
    first_line_email: Optional[str] = None
    relevant_products: Optional[list] = None
    no_website: bool = False
    exclude_flag: bool = False
    exclude_reason: Optional[str] = None
    client_tag: Optional[str] = None
    created_at: datetime


class PipelineLeadListResponse(BaseModel):
    leads: list[PipelineLeadResponse]
    total: int
    page: int = 1
    page_size: int = 50
    total_pages: int = 1


# --- Review Actions ---

class PipelineDiscardRequest(BaseModel):
    reason: Optional[str] = None


class PipelineFirstLineEdit(BaseModel):
    first_line_email: str = Field(..., min_length=1, max_length=2000)
