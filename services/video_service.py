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


async def poll_video_task(
    client: SophNetClient, sophnet_task_id: str, on_update: callable | None = None
) -> str:
    """Poll video task status until completion or timeout. Returns the video download URL."""
    max_attempts = SETTINGS.video_timeout_sec // SETTINGS.video_poll_interval_sec
    for _ in range(max_attempts):
        result = await client.query_video_task(sophnet_task_id)
        status = result.get("status", "")

        if status == "completed":
            video_url = result.get("result", {}).get("video_url", "")
            if not video_url and "result" in result and isinstance(result["result"], str):
                video_url = result["result"]
            if not video_url:
                raise SophNetError(f"Video completed but no video_url in response: {result}")
            return video_url

        if status == "failed":
            error_msg = result.get("error", "Unknown error")
            raise SophNetError(f"Video generation failed: {error_msg}")

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
    sophnet_task_id = submit_result.get("task_id") or submit_result.get("data", {}).get("task_id")
    if not sophnet_task_id:
        sophnet_task_id = (
            submit_result.get("data", {}).get("task_id")
            or submit_result.get("taskId")
        )
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