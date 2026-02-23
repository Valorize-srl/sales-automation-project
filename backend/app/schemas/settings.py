from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SettingOut(BaseModel):
    """Schema for setting response."""

    key: str
    value: str
    description: Optional[str] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    """Schema for updating a setting value."""

    value: str = Field(..., min_length=1, max_length=500)
