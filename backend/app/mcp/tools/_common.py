"""Shared helpers for MCP tool modules."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def person_to_dict(p) -> dict[str, Any]:
    return {
        "id": p.id,
        "first_name": p.first_name,
        "last_name": p.last_name,
        "email": p.email,
        "phone": p.phone,
        "linkedin_url": p.linkedin_url,
        "title": p.title,
        "company_id": p.company_id,
        "company_name": p.company_name,
        "industry": p.industry,
        "location": p.location,
        "client_tag": p.client_tag,
        "tags": p.tags,
        "list_id": p.list_id,
        "notes": p.notes,
        "enriched_at": _iso(p.enriched_at),
        "converted_at": _iso(p.converted_at),
        "created_at": _iso(p.created_at),
    }


def company_to_dict(c) -> dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "email_domain": c.email_domain,
        "phone": c.phone,
        "website": c.website,
        "linkedin_url": c.linkedin_url,
        "industry": c.industry,
        "industry_standardized": getattr(c, "industry_standardized", None),
        "location": c.location,
        "province": getattr(c, "province", None),
        "client_tag": c.client_tag,
        "tags": c.tags,
        "list_id": c.list_id,
        "notes": c.notes,
        "signals": c.signals,
        "revenue": getattr(c, "revenue", None),
        "employee_count": getattr(c, "employee_count", None),
        "revenue_band": getattr(c, "revenue_band", None),
        "employee_count_band": getattr(c, "employee_count_band", None),
        "icp_score": getattr(c, "icp_score", None),
        "priority_tier": getattr(c, "priority_tier", None),
        "lifecycle_stage": getattr(c, "lifecycle_stage", None),
        "reason_summary": getattr(c, "reason_summary", None),
        "scored_with_icp_id": getattr(c, "scored_with_icp_id", None),
        "last_scored_at": _iso(getattr(c, "last_scored_at", None)),
        "custom_fields": getattr(c, "custom_fields", None),
        "enriched_at": _iso(c.enriched_at),
        "enrichment_source": c.enrichment_source,
        "created_at": _iso(c.created_at),
    }


def campaign_to_dict(c) -> dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "status": c.status.value if hasattr(c.status, "value") else c.status,
        "instantly_campaign_id": c.instantly_campaign_id,
        "icp_id": c.icp_id,
        "subject_lines": c.subject_lines,
        "email_templates": c.email_templates,
        "total_sent": c.total_sent,
        "total_opened": c.total_opened,
        "total_replied": c.total_replied,
        "created_at": _iso(c.created_at),
        "deleted_at": _iso(c.deleted_at),
    }


def response_to_dict(r) -> dict[str, Any]:
    return {
        "id": r.id,
        "campaign_id": r.campaign_id,
        "ai_agent_id": r.ai_agent_id,
        "from_email": r.from_email,
        "sender_email": r.sender_email,
        "thread_id": r.thread_id,
        "subject": r.subject,
        "message_body": r.message_body,
        "direction": r.direction.value if hasattr(r.direction, "value") else r.direction,
        "sentiment": (r.sentiment.value if r.sentiment and hasattr(r.sentiment, "value") else r.sentiment),
        "sentiment_score": r.sentiment_score,
        "ai_suggested_reply": r.ai_suggested_reply,
        "human_approved_reply": r.human_approved_reply,
        "status": r.status.value if hasattr(r.status, "value") else r.status,
        "received_at": _iso(r.received_at),
        "created_at": _iso(r.created_at),
    }


def lead_list_to_dict(ll) -> dict[str, Any]:
    return {
        "id": ll.id,
        "name": ll.name,
        "description": ll.description,
        "client_tag": ll.client_tag,
        "ai_agent_id": ll.ai_agent_id,
        "filters_snapshot": ll.filters_snapshot,
        "people_count": ll.people_count,
        "companies_count": ll.companies_count,
        "created_at": _iso(ll.created_at),
        "updated_at": _iso(ll.updated_at),
    }


def ai_agent_to_dict(a) -> dict[str, Any]:
    return {
        "id": a.id,
        "name": a.name,
        "client_tag": a.client_tag,
        "description": a.description,
        "icp_config": a.icp_config,
        "signals_config": a.signals_config,
        "knowledge_base_text": a.knowledge_base_text,
        "knowledge_base_source": a.knowledge_base_source,
        "apollo_credits_allocated": a.apollo_credits_allocated,
        "apollo_credits_consumed": a.apollo_credits_consumed,
        "credits_remaining": a.credits_remaining,
        "is_active": a.is_active,
        "created_at": _iso(a.created_at),
        "updated_at": _iso(a.updated_at),
    }


def _iso(v: datetime | None) -> str | None:
    return v.isoformat() if v else None
