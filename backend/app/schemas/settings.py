from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SettingOut(BaseModel):
    """Schema for setting response."""

    key: str
    value: str
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    """Schema for updating a setting value."""

    value: str = Field(..., max_length=500)
