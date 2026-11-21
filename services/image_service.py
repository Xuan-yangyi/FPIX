import asyncio
import base64
import os
from services.sophnet_client import SophNetClient, SophNetError
from settings import SETTINGS


class ImageTimeoutError(Exception):
    pass


def _image_to_data_url(image_path: str) -> str:
    """Read a local image file and return a data: URL string."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}
    mime = mime_map.get(ext, "jpeg")
    return f"data:image/{mime};base64,{b64}"


async def submit_image_generation(
    client: SophNetClient,
    model: str,
    image_paths: list[str],
    prompt_text: str,
    parameters: dict | None = None,
) -> dict:
    """Submit an image generation task with optional reference images."""
    images = [_image_to_data_url(p) for p in image_paths] if image_paths else None
    if parameters is None:
        parameters = {"size": "1328*1328"}
    return await client.generate_image(model, prompt_text, images, parameters)


async def submit_image_edit(
    client: SophNetClient,
    model: str,
    image_path: str,
    prompt_text: str,
    parameters: dict | None = None,
) -> dict:
    """Submit an image editing task. Qwen-Image-Edit-2509 does NOT accept size parameters."""
    images = [_image_to_data_url(image_path)] if image_path else None
    return await client.generate_image(model, prompt_text, images, parameters)


def _extract_task_id(response: dict) -> str | None:
    """Extract task_id from SophNet image generation response.
    Response format: {"output": {"taskId": "xxx", "taskStatus": "PENDING"}}
    """
    output = response.get("output", {})
    task_id = output.get("taskId") if isinstance(output, dict) else None
    return task_id


def _extract_image_status(response: dict) -> tuple[str, str | None]:
    """Extract (status, image_url_or_error) from SophNet query response.
    Response format: {"output": {"taskId": "...", "taskStatus": "SUCCEEDED/FAILED/PENDING", "results": [{"url": "..."}]}}
    """
    output = response.get("output", {})
    status = output.get("taskStatus", "") if isinstance(output, dict) else ""

    if status in ("SUCCEEDED",):
        results = output.get("results", [])
        if isinstance(results, list) and results:
            url = results[0].get("url")
            return ("completed", url)

    if status in ("FAILED",):
        return ("failed", output.get("message", "Unknown error"))

    return ("processing", None)


async def poll_image_task(
    client: SophNetClient, task_id: str,
) -> str:
    """Poll image task status until completion or timeout. Returns the image download URL."""
    max_attempts = SETTINGS.image_timeout_sec // SETTINGS.image_poll_interval_sec
    for _ in range(max_attempts):
        response = await client.query_image_task(task_id)
        status, value = _extract_image_status(response)

        if status == "completed":
            if not value:
                raise SophNetError(f"Image completed but no image_url in response: {response}")
            return value

        if status == "failed":
            raise SophNetError(f"Image generation failed: {value}")

        await asyncio.sleep(SETTINGS.image_poll_interval_sec)

    raise ImageTimeoutError(f"Image generation timed out after {SETTINGS.image_timeout_sec}s")


async def generate_and_download_image(
    client: SophNetClient,
    model: str,
    image_paths: list[str],
    prompt_text: str,
    task_id: str,
    output_subdir: str,
    image_index: int = 0,
) -> str:
    """Full image generation pipeline: submit → poll → download. Returns local file path."""
    submit_result = await submit_image_generation(client, model, image_paths, prompt_text)

    sophnet_task_id = _extract_task_id(submit_result)
    if not sophnet_task_id:
        raise SophNetError(f"Cannot extract taskId from response: {submit_result}")

    image_url = await poll_image_task(client, sophnet_task_id)

    task_dir = os.path.join(SETTINGS.output_dir, task_id, output_subdir)
    os.makedirs(task_dir, exist_ok=True)
    ext = ".png"
    local_path = os.path.join(task_dir, f"image_{image_index:02d}{ext}")
    await client.download_file(image_url, local_path)

    return local_path