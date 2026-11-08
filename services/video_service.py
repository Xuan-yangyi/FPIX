import asyncio
import base64
import os
from services.sophnet_client import SophNetClient, SophNetError
from settings import SETTINGS


class VideoTimeoutError(Exception):
    pass


def _image_to_data_url(image_path: str) -> str:
    """Read a local image file and return a data: URL string."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}
    mime = mime_map.get(ext, "jpeg")
    return f"data:image/{mime};base64,{b64}"


async def submit_video_generation(
    client: SophNetClient,
    model: str,
    image_path: str,
    prompt_text: str,
    duration: int = 5,
    resolution: str = "720P",
) -> dict:
    """Submit a video generation task. Returns the SophNet response containing the task ID."""
    content = [
        {
            "type": "image_url",
            "role": "first_frame",
            "image_url": {"url": _image_to_data_url(image_path)},
        },
        {"type": "text", "text": prompt_text},
    ]
    parameters = {"duration": duration, "resolution": resolution}
    return await client.generate_video(model, content, parameters)


def _extract_video_status(response: dict) -> tuple[str, str | None]:
    """Extract (status, video_url_or_error) from SophNet query response.

    Handles both raw format and SophNet-wrapped format:
      Raw:   {"status": "completed", "result": {"video_url": "..."}}
      Wrapped: {"status": 0, "result": {"status": "completed", "video_url": "..."}}
    """
    inner = response.get("result", {})
    if isinstance(inner, dict) and "status" in inner and isinstance(inner["status"], str):
        # Wrapped format: status is a string inside result
        status = inner["status"]
        if status == "completed":
            url = inner.get("video_url") or inner.get("result", {}).get("video_url")
            return ("completed", url)
        elif status == "failed":
            error = inner.get("error") or inner.get("message", "Unknown error")
            return ("failed", error)
        else:
            return (status, None)
    else:
        # Raw format: status at top level
        status = str(response.get("status", ""))
        if status == "completed":
            url = response.get("result", {}).get("video_url") if isinstance(response.get("result"), dict) else None
            return ("completed", url)
        elif status == "failed":
            return ("failed", str(response.get("error", "Unknown error")))
        else:
            return ("processing", None)


async def poll_video_task(
    client: SophNetClient, sophnet_task_id: str, on_update: callable | None = None
) -> str:
    """Poll video task status until completion or timeout. Returns the video download URL."""
    max_attempts = SETTINGS.video_timeout_sec // SETTINGS.video_poll_interval_sec
    for _ in range(max_attempts):
        response = await client.query_video_task(sophnet_task_id)
        status, value = _extract_video_status(response)

        if status == "completed":
            if not value:
                raise SophNetError(f"Video completed but no video_url in response: {response}")
            return value

        if status == "failed":
            raise SophNetError(f"Video generation failed: {value}")

        if on_update:
            on_update(status)

        await asyncio.sleep(SETTINGS.video_poll_interval_sec)

    raise VideoTimeoutError(
        f"Video generation timed out after {SETTINGS.video_timeout_sec}s"
    )


async def generate_and_download(
    client: SophNetClient,
    video_task,  # VideoTask ORM instance
    model: str,
    duration: int = 5,
    resolution: str = "720P",
    on_update: callable | None = None,
) -> str:
    """Full video generation pipeline: submit → poll → download. Returns local file path."""
    submit_result = await submit_video_generation(
        client, model, video_task.input_image, video_task.prompt, duration, resolution
    )
    # SophNet response: {"status": 0, "result": {"task_id": "..."}, ...}
    inner = submit_result.get("result", {})
    sophnet_task_id = inner.get("task_id") if isinstance(inner, dict) else None
    if not sophnet_task_id:
        # fallback: try direct keys
        sophnet_task_id = submit_result.get("task_id") or submit_result.get("taskId")
    if not sophnet_task_id:
        raise SophNetError(f"Cannot extract task_id from response: {submit_result}")

    video_task.sophnet_task_id = sophnet_task_id

    video_url = await poll_video_task(client, sophnet_task_id, on_update=on_update)

    task_dir = os.path.join(SETTINGS.output_dir, video_task.task_id)
    os.makedirs(task_dir, exist_ok=True)
    ext = ".mp4"
    local_path = os.path.join(task_dir, f"shot_{video_task.shot_index}{ext}")
    await client.download_file(video_url, local_path)

    return local_path