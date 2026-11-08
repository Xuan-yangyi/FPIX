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
        """Query the status of a video generation task via POST."""
        client = await self._get_client()
        resp = await client.post(
            SETTINGS.video_query_url, json={"task_id": task_id}
        )
        resp.raise_for_status()
        return resp.json()

    async def download_file(self, url: str, dest_path: str) -> None:
        """Download a file (e.g. generated video) to local path."""
        client = await self._get_client()
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)