import json
import asyncio
import httpx
from settings import SETTINGS


class SophNetError(Exception):
    pass


class SophNetClient:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or SETTINGS.api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(SETTINGS.llm_timeout_sec),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def chat_completion(
        self, model: str, messages: list[dict], temperature: float = 0.7
    ) -> dict:
        """Call SophNet LLM chat/completions API with retry."""
        client = await self._get_client()
        last_error = None

        for attempt in range(SETTINGS.llm_retry_count + 1):
            try:
                resp = await client.post(
                    SETTINGS.llm_base_url,
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "temperature": temperature,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return {"content": content, "raw": data}
            except (httpx.HTTPError, KeyError, json.JSONDecodeError) as e:
                last_error = e
                if attempt < SETTINGS.llm_retry_count:
                    await asyncio.sleep(SETTINGS.llm_retry_delay_sec)

        raise SophNetError(f"LLM call failed after {SETTINGS.llm_retry_count + 1} attempts: {last_error}")

    async def generate_video(
        self, model: str, content: list[dict], parameters: dict | None = None
    ) -> dict:
        """Submit a video generation task to SophNet."""
        client = await self._get_client()
        body: dict = {"model": model, "content": content}
        if parameters:
            body["parameters"] = parameters

        resp = await client.post(SETTINGS.video_gen_url, json=body)
        resp.raise_for_status()
        return resp.json()

    async def query_video_task(self, task_id: str) -> dict:
        """Query the status of a video generation task via GET /task/{task_id}."""
        client = await self._get_client()
        url = SETTINGS.video_query_url.format(task_id=task_id)
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def generate_image(
        self, model: str, prompt: str, images: list[str] | None = None,
        parameters: dict | None = None
    ) -> dict:
        """Submit an image generation task to SophNet.

        Uses the unified imagegenerator/task endpoint.
        - model: 'Qwen-Image' for generation, 'Qwen-Image-Edit-2509' for editing
        - prompt: text prompt for generation/editing
        - images: list of image URLs or data URIs (optional, for reference/edit)
        """
        client = await self._get_client()
        inp: dict = {"prompt": prompt}
        if images:
            inp["images"] = images
        body: dict = {"model": model, "input": inp}
        if parameters:
            body["parameters"] = parameters

        resp = await client.post(SETTINGS.image_gen_url, json=body)
        if resp.status_code >= 400:
            body_snip = resp.text[:300] if resp.text else "(no body)"
            raise SophNetError(f"Image API {resp.status_code}: {body_snip}")
        return resp.json()

    async def query_image_task(self, task_id: str) -> dict:
        """Query the status of an image generation/editing task."""
        client = await self._get_client()
        url = SETTINGS.image_query_url.format(task_id=task_id)
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def edit_image(
        self, model: str, prompt: str, images: list[str] | None = None,
        parameters: dict | None = None
    ) -> dict:
        """Submit an image editing task (alias for generate_image with edit model)."""
        return await self.generate_image(model, prompt, images, parameters)

    async def query_edit_task(self, task_id: str) -> dict:
        """Query the status of an image editing task (alias for query_image_task)."""
        return await self.query_image_task(task_id)

    async def download_file(self, url: str, dest_path: str) -> None:
        """Download a file (e.g. generated video) to local path, retrying on auth failures."""
        # OSS signed URLs don't need the SophNet auth header — use a plain client
        last_error = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=60) as dl_client:
                    async with dl_client.stream("GET", url) as resp:
                        resp.raise_for_status()
                        with open(dest_path, "wb") as f:
                            async for chunk in resp.aiter_bytes():
                                f.write(chunk)
                        return
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 403 and attempt < 2:
                    await asyncio.sleep(2)  # OSS signed URL may need propagation
                    continue
                raise
        raise last_error  # type: ignore[misc]