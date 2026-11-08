import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Config, Task, VideoTask
from settings import SETTINGS

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def page_index(request: Request):
    return request.app.state.templates.TemplateResponse("index.html", {
        "request": request,
        "default_llm_model": SETTINGS.preferred_llm_model,
        "default_video_model": SETTINGS.preferred_video_model,
    })


@router.get("/tasks", response_class=HTMLResponse)
async def page_tasks(request: Request):
    return request.app.state.templates.TemplateResponse("tasks.html", {"request": request})


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
async def page_task_detail(request: Request, task_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        return HTMLResponse("<h2>Task not found</h2>", status_code=404)

    stmt = select(VideoTask).where(VideoTask.task_id == task_id).order_by(VideoTask.shot_index)
    result = await db.execute(stmt)
    video_tasks = result.scalars().all()

    return request.app.state.templates.TemplateResponse("task_detail.html", {
        "request": request,
        "task": {
            "id": task.id,
            "status": task.status,
            "image_paths": json.loads(task.image_paths),
            "specs": json.loads(task.specs),
            "llm_model": task.llm_model,
            "video_model": task.video_model,
            "result": json.loads(task.result),
            "error_message": task.error_message,
            "created_at": task.created_at,
        },
        "video_tasks": [
            {
                "shot_index": vt.shot_index,
                "status": vt.status,
                "video_path": vt.video_path,
            }
            for vt in video_tasks
        ],
    })


@router.get("/settings", response_class=HTMLResponse)
async def page_settings(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Config))
    configs = result.scalars().all()
    saved_config = {c.key: c.value for c in configs}

    return request.app.state.templates.TemplateResponse("settings.html", {
        "request": request,
        "saved_config": saved_config,
        "llm_models": [
            "DeepSeek-V4-Flash-Vision-Exp",
            "glm-4-flash",
            "kimi",
        ],
        "video_models": [
            "happyhorse-1.0-r2v",
            "wan2.7",
            "happyhorse-1.1-i2v",
        ],
    })


@router.get("/api/tasks-rows", response_class=HTMLResponse)
async def page_task_rows(
    request: Request,
    status: str | None = None,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
):
    per_page = 20
    stmt = select(Task).order_by(Task.created_at.desc())
    if status:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    task_list = []
    for t in tasks:
        task_list.append({
            "id": t.id,
            "status": t.status,
            "image_paths": json.loads(t.image_paths),
            "specs": json.loads(t.specs),
            "created_at": t.created_at,
        })

    return request.app.state.templates.TemplateResponse("_task_rows.html", {
        "request": request,
        "tasks": task_list,
    })