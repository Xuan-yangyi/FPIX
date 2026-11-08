from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Config

router = APIRouter(prefix="/api/config", tags=["config"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConfigUpdate(BaseModel):
    key: str
    value: str


@router.get("")
async def get_config(db: AsyncSession = Depends(get_db)):
    """Get all configuration key-value pairs."""
    result = await db.execute(select(Config))
    configs = result.scalars().all()
    return {c.key: c.value for c in configs}


@router.post("")
async def set_config(body: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    """Set a configuration value."""
    result = await db.execute(select(Config).where(Config.key == body.key))
    config = result.scalar_one_or_none()

    if config:
        config.value = body.value
        config.updated_at = _now()
    else:
        config = Config(key=body.key, value=body.value, updated_at=_now())
        db.add(config)

    await db.commit()
    return {"key": body.key, "value": body.value}