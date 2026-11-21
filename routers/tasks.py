import asyncio
import json
import os
import shutil
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, async_session
from models import Task, VideoTask
from services.workflow import execute_workflow, get_progress_queue
from settings import SETTINGS

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("/upload")
async def upload_images(
    images: list[UploadFile] = File(...),
):
    """Upload images and return file paths. Used by React frontend before task creation."""
    if not images:
        raise HTTPException(status_code=400, detail="No images provided")
    if len(images) > 9:
        raise HTTPException(status_code=400, detail="最多支持 9 张图片")

    batch_id = uuid.uuid4().hex[:8]
    batch_dir = os.path.join(SETTINGS.upload_dir, f"batch_{batch_id}")
    os.makedirs(batch_dir, exist_ok=True)

    file_paths = []
    for img in images:
        contents = await img.read()
        if len(contents) > SETTINGS.max_image_size_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"Image {img.filename} exceeds {SETTINGS.max_image_size_mb}MB limit")
        safe_name = img.filename or "image.jpg"
        file_path = os.path.join(batch_dir, safe_name)
        with open(file_path, "wb") as f:
            f.write(contents)
        file_paths.append(file_path)

    return {"file_paths": file_paths, "batch_id": batch_id}


@router.post("/json")
async def create_task_json(request: Request, db: AsyncSession = Depends(get_db)):
    """Create a new task from JSON body (React frontend)."""
    body = await request.json()

    workflow_type = body.get("workflow_type", "video")
    image_paths = body.get("image_paths", [])
    params = body.get("params", {})
    user_requirements = body.get("user_requirements", "")
    llm_model = body.get("llm_model", SETTINGS.preferred_llm_model)
    video_model = body.get("video_model", SETTINGS.preferred_video_model)
    image_model = body.get("image_model", "")  # empty -> backend uses per-workflow default
    specs = body.get("specs", {})

    # Validate images exist
    for p in image_paths:
        if not os.path.exists(p):
            raise HTTPException(status_code=400, detail=f"Image not found: {p}")

    task = Task(
        workflow_type=workflow_type,
        llm_model=llm_model,
        video_model=video_model,
        image_model=image_model,
        specs=json.dumps(specs, ensure_ascii=False),
        params=json.dumps(params, ensure_ascii=False),
        user_requirements=user_requirements,
        image_paths=json.dumps(image_paths, ensure_ascii=False),
    )
    db.add(task)
    await db.commit()

    asyncio.create_task(execute_workflow(task.id))

    return {"task_id": task.id, "status": "pending"}


@router.get("/{task_id}/progress")
async def task_progress(task_id: str):
    """SSE endpoint for real-time task progress updates."""
    async def event_stream():
        q = get_progress_queue(task_id)
        # Send initial connection event
        yield f"data: {json.dumps({'stage': 'connected', 'message': 'SSE connected'})}\n\n"

        # Send current task state if already progressed
        async with async_session() as db:
            task = await db.get(Task, task_id)
            if task:
                current_result = {}
                if task.result:
                    try:
                        current_result = json.loads(task.result)
                    except (json.JSONDecodeError, TypeError):
                        current_result = {}
                if current_result:
                    yield f"data: {json.dumps({'stage': task.status, **current_result})}\n\n"
                if task.status == "completed":
                    yield f"data: {json.dumps({'stage': 'completed', 'result_images': current_result.get('result_images', [])})}\n\n"
                    return
                if task.status == "failed":
                    yield f"data: {json.dumps({'stage': 'failed', 'error': task.error_message})}\n\n"
                    return

        try:
            while True:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("stage") in ("completed", "failed"):
                    break
        except asyncio.TimeoutError:
            # Send keepalive
            yield f"data: {json.dumps({'stage': 'processing'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/gallery/list")
async def gallery(db: AsyncSession = Depends(get_db)):
    """Return recent completed tasks for the homepage gallery."""
    stmt = (
        select(Task)
        .where(Task.status == "completed")
        .order_by(Task.created_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return {
        "tasks": [
            {
                "id": t.id,
                "workflow_type": t.workflow_type,
                "status": t.status,
                "result": json.loads(t.result),
                "created_at": t.created_at,
            }
            for t in tasks
        ]
    }


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