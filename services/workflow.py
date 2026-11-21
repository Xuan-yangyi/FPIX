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
from services.llm_service import (
    analyze_product_image,
    generate_image_prompts,
    generate_promo_texts,
    generate_storyboard,
    parse_edit_instruction,
)
from services.sophnet_client import SophNetClient, SophNetError
from services.video_service import generate_and_download
from services.image_service import generate_and_download_image, submit_image_edit, poll_image_task, _extract_task_id
from settings import SETTINGS

# In-memory progress queues for SSE (task_id -> asyncio.Queue)
_progress_queues: dict[str, asyncio.Queue] = {}


def get_progress_queue(task_id: str) -> asyncio.Queue:
    """Get or create a progress queue for SSE streaming."""
    if task_id not in _progress_queues:
        _progress_queues[task_id] = asyncio.Queue(maxsize=100)
    return _progress_queues[task_id]


def remove_progress_queue(task_id: str):
    """Clean up progress queue after task completes."""
    _progress_queues.pop(task_id, None)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _broadcast_progress(task_id: str, stage: str, **extra):
    """Send a progress event to the SSE queue."""
    q = get_progress_queue(task_id)
    event = {"stage": stage, **extra}
    try:
        q.put_nowait(event)
    except asyncio.QueueFull:
        pass  # drop if consumer is too slow


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


def _image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def execute_workflow(task_id: str) -> None:
    """Dispatch to the correct workflow based on task.workflow_type."""
    async with async_session() as db:
        result = await db.execute(select(Config).where(Config.key == "api_key"))
        config_row = result.scalar_one_or_none()
        api_key = config_row.value if config_row else ""
    client = SophNetClient(api_key=api_key)

    try:
        async with async_session() as db:
            task = await db.get(Task, task_id)
            if not task:
                return

        workflow_type = task.workflow_type

        if workflow_type == "product_set":
            await _run_product_set(client, task_id)
        elif workflow_type == "remove_bg":
            await _run_remove_bg(client, task_id)
        elif workflow_type == "model":
            await _run_model(client, task_id)
        elif workflow_type == "edit":
            await _run_edit(client, task_id)
        else:
            await _run_video(client, task_id)

    except Exception as e:
        error_detail = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        await _update_task_error(task_id, error_detail)
        await _broadcast_progress(task_id, "failed", error=error_detail)
    finally:
        await client.close()
        remove_progress_queue(task_id)


async def _run_product_set(client: SophNetClient, task_id: str):
    """Product set workflow: analyze -> prompts -> batch image generation."""
    async with async_session() as db:
        task = await db.get(Task, task_id)
        if not task:
            return
        image_paths = json.loads(task.image_paths)
        llm_model = task.llm_model
        image_model = task.image_model or "Qwen-Image"
        params = json.loads(task.params)
        user_requirements = task.user_requirements or ""

    if not image_paths:
        raise ValueError("No input images provided")

    # Stage 1: Analyze product image
    await _update_task_status(task_id, "processing", stage="analyzing")
    await _broadcast_progress(task_id, "analyzing", message="正在分析商品图片...")
    image_b64 = _image_to_base64(image_paths[0])
    analysis = await analyze_product_image(client, llm_model, image_b64)
    await _update_task_status(task_id, "processing", image_analysis=analysis)

    # Stage 2: Generate image prompts
    await _broadcast_progress(task_id, "writing", message="正在生成场景描述...")
    params["requirements"] = user_requirements
    prompts = await generate_image_prompts(client, llm_model, analysis, params)

    # Stage 3: Batch image generation
    # Collect all generation tasks: white_bg + scenes + selling_points + details + size_chart
    generation_tasks = []

    # White background
    if prompts.get("white_bg", {}).get("en_prompt"):
        generation_tasks.append(("white_bg", prompts["white_bg"]["en_prompt"]))

    # Scenes
    for scene in prompts.get("scenes", []):
        if scene.get("en_prompt"):
            generation_tasks.append(("scene", scene["en_prompt"]))

    # Selling points
    for sp in prompts.get("selling_points", []):
        if sp.get("en_prompt"):
            generation_tasks.append(("selling_point", sp["en_prompt"]))

    # Details
    for d in prompts.get("details", []):
        if d.get("en_prompt"):
            generation_tasks.append(("detail", d["en_prompt"]))

    # Size chart
    if prompts.get("size_chart", {}).get("en_prompt"):
        generation_tasks.append(("size_chart", prompts["size_chart"]["en_prompt"]))

    total_images = len(generation_tasks)
    await _broadcast_progress(task_id, "generating", current=0, total=total_images,
                              message=f"正在生成 {total_images} 张图片...")

    result_images = []
    for idx, (img_type, prompt) in enumerate(generation_tasks):
        await _broadcast_progress(task_id, "generating", current=idx + 1, total=total_images,
                                  image_type=img_type, message=f"正在生成: {img_type} ({idx+1}/{total_images})")

        local_path = await generate_and_download_image(
            client, image_model, image_paths, prompt,
            task_id=task_id, output_subdir=f"{img_type}s", image_index=idx,
        )
        result_images.append({"type": img_type, "path": local_path})

        # Send preview URL for immediate display
        relative_path = local_path.replace(SETTINGS.output_dir, "/outputs")
        await _broadcast_progress(task_id, "generating", current=idx + 1, total=total_images,
                                  image_type=img_type, preview_url=relative_path)

    await _update_task_status(task_id, "completed", result_images=result_images)
    await _broadcast_progress(task_id, "completed", result_images=[
        {"type": r["type"], "path": r["path"].replace(SETTINGS.output_dir, "/outputs")}
        for r in result_images
    ])


async def _run_remove_bg(client: SophNetClient, task_id: str):
    """Remove background workflow: edit API to remove background."""
    async with async_session() as db:
        task = await db.get(Task, task_id)
        if not task:
            return
        image_paths = json.loads(task.image_paths)
        params = json.loads(task.params)
        image_model = task.image_model or "Qwen-Image"

    if not image_paths:
        raise ValueError("No input image provided")

    output_format = params.get("output_format", "both")  # "transparent", "white_bg", "both"
    result_images = []

    await _update_task_status(task_id, "processing", stage="removing_bg")
    await _broadcast_progress(task_id, "removing_bg", message="正在去除背景...")

    # Background removal prompt
    remove_bg_prompt = "Remove the background from this product image. Make the background completely transparent while keeping every detail of the product intact. The product edges should be sharp and clean. Output a transparent PNG."

    submit_result = await submit_image_edit(client, image_model, image_paths[0], remove_bg_prompt)

    st_id = _extract_task_id(submit_result)
    if not st_id:
        raise SophNetError(f"Cannot extract task_id from response: {submit_result}")

    image_url = await poll_image_task(client, st_id)

    task_dir = os.path.join(SETTINGS.output_dir, task_id)
    os.makedirs(task_dir, exist_ok=True)
    transparent_path = os.path.join(task_dir, "transparent.png")
    await client.download_file(image_url, transparent_path)
    result_images.append({"type": "transparent", "path": transparent_path})

    await _broadcast_progress(task_id, "removing_bg", preview_url=transparent_path.replace(SETTINGS.output_dir, "/outputs"))

    if output_format in ("white_bg", "both"):
        await _broadcast_progress(task_id, "removing_bg", message="正在生成白底图...")
        # Generate white background version
        white_bg_prompt = "Place this product on a pure white background (#FFFFFF). Keep the product exactly as is. Clean e-commerce product photography style."
        submit_result2 = await submit_image_edit(client, image_model, transparent_path, white_bg_prompt)
        st_id2 = _extract_task_id(submit_result2)
        if st_id2:
            image_url2 = await poll_image_task(client, st_id2)
            white_path = os.path.join(task_dir, "white_bg.png")
            await client.download_file(image_url2, white_path)
            result_images.append({"type": "white_bg", "path": white_path})

    await _update_task_status(task_id, "completed", result_images=[
        {"type": r["type"], "path": r["path"].replace(SETTINGS.output_dir, "/outputs")}
        for r in result_images
    ])
    await _broadcast_progress(task_id, "completed", result_images=[
        {"type": r["type"], "path": r["path"].replace(SETTINGS.output_dir, "/outputs")}
        for r in result_images
    ])


async def _run_model(client: SophNetClient, task_id: str):
    """Model replacement workflow: analyze -> targeted edit -> multiple variants."""
    async with async_session() as db:
        task = await db.get(Task, task_id)
        if not task:
            return
        image_paths = json.loads(task.image_paths)
        llm_model = task.llm_model
        image_model = task.image_model or "Qwen-Image"
        params = json.loads(task.params)
        user_requirements = task.user_requirements or ""

    if not image_paths:
        raise ValueError("No input image provided")

    # Stage 1: Analyze current image
    await _broadcast_progress(task_id, "analyzing", message="正在分析图片...")
    image_b64 = _image_to_base64(image_paths[0])
    analysis = await analyze_product_image(client, llm_model, image_b64)

    # Stage 2: Parse replacement instruction
    replacement_desc = params.get("replacement_desc", user_requirements)
    if not replacement_desc:
        replacement_desc = "Replace the background with a modern, clean e-commerce scene"
    num_variants = params.get("num_variants", 3)

    edit_parsed = await parse_edit_instruction(client, llm_model, replacement_desc,
                                                json.dumps(analysis, ensure_ascii=False))

    # Stage 3: Generate multiple variants
    result_images = []
    total = num_variants
    await _broadcast_progress(task_id, "generating", current=0, total=total,
                              message=f"正在生成 {num_variants} 个变体...")

    for i in range(num_variants):
        await _broadcast_progress(task_id, "generating", current=i + 1, total=total,
                                  message=f"正在生成变体 {i+1}/{num_variants}")

        prompt = edit_parsed.get("en_prompt", replacement_desc)
        # Add slight variation
        if i > 0:
            prompt += f" Variation {i+1}: slightly different angle and lighting."

        submit_result = await submit_image_edit(client, image_model, image_paths[0], prompt)
        st_id = _extract_task_id(submit_result)
        if not st_id:
            raise SophNetError(f"Cannot extract task_id: {submit_result}")

        image_url = await poll_image_task(client, st_id)

        task_dir = os.path.join(SETTINGS.output_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)
        local_path = os.path.join(task_dir, f"variant_{i+1:02d}.png")
        await client.download_file(image_url, local_path)
        result_images.append({"type": "variant", "index": i + 1, "path": local_path})

        rel_path = local_path.replace(SETTINGS.output_dir, "/outputs")
        await _broadcast_progress(task_id, "generating", current=i + 1, total=total,
                                  preview_url=rel_path)

    await _update_task_status(task_id, "completed", result_images=[
        {"type": r["type"], "index": r["index"], "path": r["path"].replace(SETTINGS.output_dir, "/outputs")}
        for r in result_images
    ])
    await _broadcast_progress(task_id, "completed", result_images=[
        {"type": r["type"], "index": r["index"], "path": r["path"].replace(SETTINGS.output_dir, "/outputs")}
        for r in result_images
    ])


async def _run_edit(client: SophNetClient, task_id: str):
    """AI edit workflow: parse natural language -> edit image."""
    async with async_session() as db:
        task = await db.get(Task, task_id)
        if not task:
            return
        image_paths = json.loads(task.image_paths)
        llm_model = task.llm_model
        image_model = task.image_model or "Qwen-Image"
        params = json.loads(task.params)
        user_requirements = task.user_requirements or ""

    if not image_paths:
        raise ValueError("No input image provided")

    instruction = params.get("edit_instruction", user_requirements)
    if not instruction:
        raise ValueError("No edit instruction provided")

    await _broadcast_progress(task_id, "analyzing", message="正在分析编辑指令...")

    # Parse instruction
    image_b64 = _image_to_base64(image_paths[0])
    analysis = await analyze_product_image(client, llm_model, image_b64)
    edit_parsed = await parse_edit_instruction(client, llm_model, instruction,
                                                json.dumps(analysis, ensure_ascii=False))

    await _broadcast_progress(task_id, "editing", message="正在编辑图片...")

    prompt = edit_parsed.get("en_prompt", instruction)
    submit_result = await submit_image_edit(client, image_model, image_paths[0], prompt)

    st_id = _extract_task_id(submit_result)
    if not st_id:
        raise SophNetError(f"Cannot extract task_id: {submit_result}")

    image_url = await poll_image_task(client, st_id)

    task_dir = os.path.join(SETTINGS.output_dir, task_id)
    os.makedirs(task_dir, exist_ok=True)
    result_path = os.path.join(task_dir, "edited.png")
    await client.download_file(image_url, result_path)

    rel_path = result_path.replace(SETTINGS.output_dir, "/outputs")
    await _update_task_status(task_id, "completed", result_images=[
        {"type": "edited", "path": rel_path}
    ])
    await _broadcast_progress(task_id, "completed", result_images=[
        {"type": "edited", "path": rel_path}
    ])


async def _run_video(client: SophNetClient, task_id: str):
    """Video workflow: analysis -> promo texts -> storyboard -> video generation."""
    async with async_session() as db:
        task = await db.get(Task, task_id)
        if not task:
            return
        image_paths = json.loads(task.image_paths)
        specs = json.loads(task.specs)
        user_requirements = task.user_requirements or ""
        llm_model = task.llm_model
        video_model = task.video_model

    # Stage 1: Image Analysis
    await _update_task_status(task_id, "processing", stage="analyzing")
    await _broadcast_progress(task_id, "analyzing", message="正在分析商品图片...")
    image_b64 = _image_to_base64(image_paths[0])
    analysis = await analyze_product_image(client, llm_model, image_b64)
    await _update_task_status(task_id, "processing", image_analysis=analysis)

    # Stage 2: Promo Texts
    await _broadcast_progress(task_id, "writing", message="正在生成宣传文案...")
    promo_texts = await generate_promo_texts(client, llm_model, analysis, specs, user_requirements)
    await _update_task_status(task_id, "processing", promo_texts=promo_texts)

    # Stage 3: Storyboard
    await _broadcast_progress(task_id, "storyboard", message="正在设计视频分镜...")
    product_info = json.dumps({"analysis": analysis, "specs": specs}, ensure_ascii=False)
    storyboard = await generate_storyboard(client, llm_model, product_info, promo_texts, user_requirements)
    await _update_task_status(task_id, "processing", storyboard=storyboard)

    # Stage 4: Video Generation
    await _broadcast_progress(task_id, "generating_video", message="正在生成视频...")

    # Serialize storyboard (list of shots) into a single prompt for 15-second video
    if isinstance(storyboard, list) and storyboard:
        # Combine all shots into narrative prompt
        combined_prompt = json.dumps(storyboard, ensure_ascii=False) if storyboard else ""
    else:
        combined_prompt = ""

    async with async_session() as db:
        vt = VideoTask(
            task_id=task_id,
            shot_index="0",
            prompt=combined_prompt,
            input_image=image_paths[0] if image_paths else "",
            status="pending",
        )
        db.add(vt)
        await db.commit()

    videos_result = []
    vt.status = "processing"
    try:
        local_path = await generate_and_download(
            client, vt, video_model,
            image_paths=image_paths,
            duration=15, resolution="720P", ratio="16:9",
        )
        vt.status = "completed"
        vt.video_path = local_path
        vt.updated_at = _now()
        videos_result.append({"path": local_path, "status": "completed"})
    except Exception as e:
        vt.status = "failed"
        vt.updated_at = _now()
        videos_result.append({"path": "", "status": "failed", "error": str(e)})

    async with async_session() as db:
        vt_db = await db.get(VideoTask, vt.id)
        if vt_db:
            vt_db.status = vt.status
            vt_db.video_path = vt.video_path
            vt_db.sophnet_task_id = vt.sophnet_task_id
            vt_db.updated_at = vt.updated_at
            await db.commit()

    rel_path = videos_result[0]["path"].replace(SETTINGS.output_dir, "/outputs") if videos_result else ""
    result_images = [{"type": "video", "path": rel_path}]
    await _update_task_status(task_id, "completed", result_images=result_images)
    await _broadcast_progress(task_id, "completed", result_images=result_images, type="video")
