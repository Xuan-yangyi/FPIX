import asyncio
import base64
import json
import os
import traceback
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from models import Config, Task, VideoTask
from services.llm_service import analyze_image, generate_promo_texts, generate_storyboard
from services.sophnet_client import SophNetClient, SophNetError
from services.video_service import generate_and_download


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _update_task_status(task_id: str, status: str, **extra):
    """Update task status and optionally merge into result JSON."""
    async with async_session() as db:
        task = await db.get(Task, task_id)
        if task:
            task.status = status
            task.updated_at = _now()
            if extra:
                current_result = json.loads(task.result)
                current_result.update(extra)
                task.result = json.dumps(current_result, ensure_ascii=False)
            await db.commit()


async def _update_task_error(task_id: str, error: str):
    async with async_session() as db:
        task = await db.get(Task, task_id)
        if task:
            task.status = "failed"
            task.error_message = error
            task.updated_at = _now()
            await db.commit()


async def _create_video_tasks(db: AsyncSession, task_id: str, storyboard: list, image_paths: list):
    """Create VideoTask rows for each storyboard shot."""
    main_image = image_paths[0] if image_paths else ""
    for shot in storyboard:
        vt = VideoTask(
            task_id=task_id,
            shot_index=str(shot["shot_number"] - 1),
            prompt=shot.get("en_prompt", shot.get("cn_prompt", "")),
            input_image=main_image,
            status="pending",
        )
        db.add(vt)
    await db.commit()


def _image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def execute_workflow(task_id: str) -> None:
    """Execute the full 4-stage workflow for a task."""
    # Load API key from database (user may have set it via settings page)
    async with async_session() as db:
        result = await db.execute(select(Config).where(Config.key == "api_key"))
        config_row = result.scalar_one_or_none()
        api_key = config_row.value if config_row else ""
    client = SophNetClient(api_key=api_key)
    try:
        # Load task
        async with async_session() as db:
            task = await db.get(Task, task_id)
            if not task:
                return
            image_paths = json.loads(task.image_paths)
            specs = json.loads(task.specs)
            llm_model = task.llm_model
            video_model = task.video_model

        # --- Stage 1: Image Analysis ---
        await _update_task_status(task_id, "analyzing")
        image_b64 = _image_to_base64(image_paths[0])
        analysis = await analyze_image(client, llm_model, image_b64)
        await _update_task_status(task_id, "analyzing", image_analysis=analysis)

        # --- Stage 2: Promo Texts ---
        await _update_task_status(task_id, "writing")
        promo_texts = await generate_promo_texts(client, llm_model, analysis, specs)
        await _update_task_status(task_id, "writing", promo_texts=promo_texts)

        # --- Stage 3: Storyboard ---
        await _update_task_status(task_id, "storyboard")
        product_info = json.dumps({"analysis": analysis, "specs": specs}, ensure_ascii=False)
        storyboard = await generate_storyboard(client, llm_model, product_info, promo_texts)
        await _update_task_status(task_id, "storyboard", storyboard=storyboard)

        # --- Stage 4: Video Generation ---
        await _update_task_status(task_id, "generating_video")
        async with async_session() as db:
            await _create_video_tasks(db, task_id, storyboard, image_paths)

        videos_result = []
        for shot in storyboard:
            shot_index = shot["shot_number"] - 1

            async with async_session() as db:
                stmt = select(VideoTask).where(
                    VideoTask.task_id == task_id,
                    VideoTask.shot_index == str(shot_index),
                )
                result = await db.execute(stmt)
                vt = result.scalar_one_or_none()
                if vt is None:
                    continue

            m_image = image_paths[0]
            en_prompt = shot.get("en_prompt", shot.get("cn_prompt", ""))

            try:
                vt.status = "processing"
                local_path = await generate_and_download(
                    client, vt, video_model, duration=5, resolution="720P"
                )
                vt.status = "completed"
                vt.video_path = local_path
                vt.updated_at = _now()
                videos_result.append({
                    "shot_index": shot_index,
                    "path": local_path,
                    "status": "completed",
                })
            except Exception as e:
                vt.status = "failed"
                vt.updated_at = _now()
                videos_result.append({
                    "shot_index": shot_index,
                    "path": "",
                    "status": "failed",
                    "error": str(e),
                })

            async with async_session() as db:
                vt_db = await db.get(VideoTask, vt.id)
                if vt_db:
                    vt_db.status = vt.status
                    vt_db.video_path = vt.video_path
                    vt_db.sophnet_task_id = vt.sophnet_task_id
                    vt_db.updated_at = vt.updated_at
                    await db.commit()

        await _update_task_status(task_id, "completed", videos=videos_result)

    except Exception as e:
        error_detail = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        await _update_task_error(task_id, error_detail)
    finally:
        await client.close()