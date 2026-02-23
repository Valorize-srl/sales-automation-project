from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.settings import Setting
from app.schemas.settings import SettingOut, SettingUpdate

router = APIRouter()


@router.get("/{key}", response_model=SettingOut)
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single setting by key."""
    query = select(Setting).where(Setting.key == key)
    result = await db.execute(query)
    setting = result.scalar_one_or_none()

    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    return SettingOut.model_validate(setting)


@router.put("/{key}", response_model=SettingOut)
async def update_setting(
    key: str,
    update: SettingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a setting value."""
    query = select(Setting).where(Setting.key == key)
    result = await db.execute(query)
    setting = result.scalar_one_or_none()

    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    setting.value = update.value
    await db.commit()
    await db.refresh(setting)

    return SettingOut.model_validate(setting)
