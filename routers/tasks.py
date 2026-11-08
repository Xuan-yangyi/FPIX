import asyncio
import json
import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Task, VideoTask
from services.workflow import execute_workflow
from settings import SETTINGS

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("")
async def create_task(
    request: Request,
    images: list[UploadFile] = File(...),
    specs: str = Form(...),
    llm_model: str = Form(default=SETTINGS.preferred_llm_model),
    video_model: str = Form(default=SETTINGS.preferred_video_model),
    db: AsyncSession = Depends(get_db),
):
    """Create a new task: upload images + specs, trigger async workflow."""
    for img in images:
        contents = await img.read()
        if len(contents) > SETTINGS.max_image_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"Image {img.filename} exceeds {SETTINGS.max_image_size_mb}MB limit",
            )
        await img.seek(0)

    task = Task(
        llm_model=llm_model,
        video_model=video_model,
        specs=specs,
    )
    db.add(task)
    await db.flush()

    task_dir = os.path.join(SETTINGS.upload_dir, task.id)
    os.makedirs(task_dir, exist_ok=True)
    image_paths = []
    for img in images:
        file_path = os.path.join(task_dir, img.filename or "image.jpg")
        contents = await img.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        image_paths.append(file_path)

    task.image_paths = json.dumps(image_paths, ensure_ascii=False)
    await db.commit()

    asyncio.create_task(execute_workflow(task.id))

    # HTMX form submission: use HX-Redirect for full page navigation
    if request.headers.get("hx-request"):
        return Response(
            status_code=200,
            headers={"HX-Redirect": f"/tasks/{task.id}"},
        )
    return {"task_id": task.id, "status": "pending"}


@router.get("")
async def list_tasks(
    status: str | None = None,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """List tasks with optional status filter and pagination."""
    per_page = 20
    stmt = select(Task).order_by(Task.created_at.desc())
    if status:
        stmt = stmt.where(Task.status == status)

    count_stmt = select(func.count()).select_from(Task)
    if status:
        count_stmt = count_stmt.where(Task.status == status)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return {
        "tasks": [
            {
                "id": t.id,
                "status": t.status,
                "image_paths": json.loads(t.image_paths),
                "specs": json.loads(t.specs),
                "llm_model": t.llm_model,
                "video_model": t.video_model,
                "error_message": t.error_message,
                "created_at": t.created_at,
            }
            for t in tasks
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{task_id}")
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get full task details including result and video tasks."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    stmt = select(VideoTask).where(VideoTask.task_id == task_id).order_by(VideoTask.shot_index)
    result = await db.execute(stmt)
    video_tasks = result.scalars().all()

    return {
        "id": task.id,
        "status": task.status,
        "image_paths": json.loads(task.image_paths),
        "specs": json.loads(task.specs),
        "llm_model": task.llm_model,
        "video_model": task.video_model,
        "result": json.loads(task.result),
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "video_tasks": [
            {
                "id": vt.id,
                "shot_index": vt.shot_index,
                "prompt": vt.prompt,
                "status": vt.status,
                "video_path": vt.video_path,
                "sophnet_task_id": vt.sophnet_task_id,
            }
            for vt in video_tasks
        ],
    }


@router.delete("/{task_id}")
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a task and its associated files."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    upload_dir = os.path.join(SETTINGS.upload_dir, task_id)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)
    output_dir = os.path.join(SETTINGS.output_dir, task_id)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    stmt = select(VideoTask).where(VideoTask.task_id == task_id)
    result = await db.execute(stmt)
    for vt in result.scalars().all():
        await db.delete(vt)

    await db.delete(task)
    await db.commit()
    return {"deleted": True}


@router.post("/{task_id}/retry")
async def retry_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Retry a failed task."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")

    task.status = "pending"
    task.error_message = None
    task.result = "{}"
    task.updated_at = datetime.now(timezone.utc).isoformat()
    await db.commit()

    asyncio.create_task(execute_workflow(task.id))
    return {"task_id": task.id, "status": "pending"}


@router.get("/{task_id}/videos/{shot_index}")
async def download_video(task_id: str, shot_index: str, db: AsyncSession = Depends(get_db)):
    """Download a generated video file."""
    stmt = select(VideoTask).where(
        VideoTask.task_id == task_id,
        VideoTask.shot_index == shot_index,
    )
    result = await db.execute(stmt)
    vt = result.scalar_one_or_none()
    if not vt or not vt.video_path or not os.path.exists(vt.video_path):
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(vt.video_path, media_type="video/mp4", filename=f"shot_{shot_index}.mp4")