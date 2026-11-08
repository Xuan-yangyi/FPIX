from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Config

router = APIRouter(prefix="/api/config", tags=["config"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate_middle(s: str, max_len: int = 20) -> str:
    if len(s) <= max_len:
        return s
    return s[:8] + "..." + s[-8:]


def _render_config_html(data: dict) -> str:
    api_key = data.get("api_key", "")
    llm = data.get("preferred_llm_model", "未设置")
    video = data.get("preferred_video_model", "未设置")
    key_display = _truncate_middle(api_key) if api_key else "未设置"

    return f"""<table>
        <tr><th>API Key</th><td>{key_display} {'✅ 已保存' if api_key else '❌ 未设置'}</td></tr>
        <tr><th>默认 LLM 模型</th><td>{llm}</td></tr>
        <tr><th>默认视频模型</th><td>{video}</td></tr>
    </table>"""


async def _load_config(db: AsyncSession) -> dict:
    result = await db.execute(select(Config))
    configs = result.scalars().all()
    return {c.key: c.value for c in configs}


async def _save_config(db: AsyncSession, key: str, value: str):
    result = await db.execute(select(Config).where(Config.key == key))
    config = result.scalar_one_or_none()
    if config:
        config.value = value
        config.updated_at = _now()
    else:
        config = Config(key=key, value=value, updated_at=_now())
        db.add(config)
    await db.commit()


# ── JSON API ──

class ConfigUpdate(BaseModel):
    key: str
    value: str


@router.get("")
async def get_config_json(db: AsyncSession = Depends(get_db)):
    return await _load_config(db)


@router.post("")
async def set_config_json(body: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    await _save_config(db, body.key, body.value)
    return {"key": body.key, "value": body.value}


# ── HTMX form endpoints ──

@router.get("/view", response_class=HTMLResponse)
async def get_config_view(db: AsyncSession = Depends(get_db)):
    data = await _load_config(db)
    return _render_config_html(data)


@router.post("/form", response_class=HTMLResponse)
async def set_config_form(
    key: str = Form(...),
    value: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    await _save_config(db, key, value)
    data = await _load_config(db)
    return _render_config_html(data)