# 电商AI内容生产工具 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个人使用的 Web 工具，上传产品图片+规格后自动生成宣传文案、分镜头脚本和 AI 宣传视频。

**Architecture:** FastAPI 单服务，Jinja2 模板 + HTMX 前端，SQLite 存储，通过 SophNet API 统一调用 LLM 和视频模型，asyncio.create_task 后台编排工作流。

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy (async), aiosqlite, httpx, Jinja2, HTMX (CDN), Pico.css (CDN)

**Spec:** `docs/superpowers/specs/2026-11-08-dianshang-ai-content-generator-design.md`

## Global Constraints

- 单用户个人工具, 无认证系统
- 部署: `python app.py` 一键启动
- 图片 ≤ 20MB
- 视频轮询超时 10 分钟
- API Key 存 SQLite, 不提交 git
- 同时最多 1 个活跃任务

---

## 文件结构概览

| 文件 | 职责 |
|------|------|
| `requirements.txt` | 依赖声明 |
| `.env.example` | 环境变量模板 |
| `.gitignore` | Git 忽略规则 |
| `settings.py` | 全局配置读取 |
| `database.py` | SQLite 初始化与 session |
| `models.py` | SQLAlchemy ORM 模型 |
| `services/sophnet_client.py` | SophNet HTTP 封装 (LLM + Video) |
| `services/llm_service.py` | Prompt 链与 LLM 调用 |
| `services/video_service.py` | 视频生成提交/轮询/下载 |
| `services/workflow.py` | 主流程编排 |
| `routers/pages.py` | 页面路由 (Jinja2) |
| `routers/tasks.py` | 任务 CRUD API |
| `routers/config.py` | 配置 API |
| `templates/base.html` | 公共布局 |
| `templates/index.html` | 主页 — 创建任务 |
| `templates/tasks.html` | 任务列表 |
| `templates/task_detail.html` | 任务详情 |
| `templates/settings.html` | 设置页 |
| `static/style.css` | 自定义样式 |
| `app.py` | 应用入口 |

---

### Task 1: 项目骨架与依赖

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `settings.py`
- Create: `database.py`
- Create: `models.py`

**Interfaces:**
- Produces: `settings.SETTINGS` (dataclass: api_key, preferred_llm_model, preferred_video_model)
- Produces: `database.init_db()` → 创建表
- Produces: `database.get_db()` → AsyncGenerator[AsyncSession]
- Produces: `models.Task`, `models.VideoTask`, `models.Config` (SQLAlchemy models)

- [ ] **Step 1: 创建 requirements.txt**

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy[asyncio]==2.0.35
aiosqlite==0.20.0
httpx==0.27.2
python-multipart==0.0.12
jinja2==3.1.4
pydantic==2.9.2
pydantic-settings==2.5.2
aiofiles==24.1.0
```

- [ ] **Step 2: 创建 .env.example**

```
SOPHNET_API_KEY=your_api_key_here
PREFERRED_LLM_MODEL=DeepSeek-V4-Flash-Vision-Exp
PREFERRED_VIDEO_MODEL=happyhorse-1.1-i2v
```

- [ ] **Step 3: 创建 .gitignore**

```
__pycache__/
*.pyc
.env
data.db
uploads/
outputs/
.venv/
```

- [ ] **Step 4: 创建 settings.py**

```python
import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("SOPHNET_API_KEY", ""))
    preferred_llm_model: str = field(
        default_factory=lambda: os.getenv("PREFERRED_LLM_MODEL", "DeepSeek-V4-Flash-Vision-Exp")
    )
    preferred_video_model: str = field(
        default_factory=lambda: os.getenv("PREFERRED_VIDEO_MODEL", "happyhorse-1.1-i2v")
    )

    # SophNet endpoints
    llm_base_url: str = "https://www.sophnet.com/api/open-apis/v1/chat/completions"
    video_gen_url: str = "https://www.sophnet.com/api/open-apis/projects/easyllms/videogenerator/generate"
    video_query_url: str = "https://www.sophnet.com/api/open-apis/projects/easyllms/videogenerator/query"

    # File storage
    upload_dir: str = "uploads"
    output_dir: str = "outputs"
    database_url: str = "sqlite+aiosqlite:///data.db"

    # Limits
    max_image_size_mb: int = 20
    video_poll_interval_sec: int = 5
    video_timeout_sec: int = 600
    llm_retry_count: int = 2
    llm_retry_delay_sec: int = 3
    llm_timeout_sec: int = 120
    max_concurrent_tasks: int = 1


SETTINGS = Settings()

# Ensure storage dirs exist
os.makedirs(SETTINGS.upload_dir, exist_ok=True)
os.makedirs(SETTINGS.output_dir, exist_ok=True)
```

- [ ] **Step 5: 创建 database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from settings import SETTINGS

engine = create_async_engine(SETTINGS.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    from models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session() as session:
        yield session
```

- [ ] **Step 6: 创建 models.py**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Text
from sqlalchemy.orm import DeclarativeBase

from database import engine


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Text, primary_key=True, default=_uuid)
    status = Column(Text, nullable=False, default="pending")
    image_paths = Column(Text, nullable=False, default="[]")       # JSON array
    specs = Column(Text, nullable=False, default="{}")              # JSON object
    llm_model = Column(Text, nullable=False, default="")
    video_model = Column(Text, nullable=False, default="")
    result = Column(Text, nullable=False, default="{}")             # JSON object
    error_message = Column(Text, nullable=True)
    created_at = Column(Text, nullable=False, default=_now)
    updated_at = Column(Text, nullable=False, default=_now)


class VideoTask(Base):
    __tablename__ = "video_tasks"

    id = Column(Text, primary_key=True, default=_uuid)
    task_id = Column(Text, nullable=False, index=True)
    shot_index = Column(Text, nullable=False)                       # "0", "1", ...
    prompt = Column(Text, nullable=False, default="")
    input_image = Column(Text, nullable=False, default="")
    video_path = Column(Text, nullable=False, default="")
    status = Column(Text, nullable=False, default="pending")
    sophnet_task_id = Column(Text, nullable=True)
    created_at = Column(Text, nullable=False, default=_now)
    updated_at = Column(Text, nullable=False, default=_now)


class Config(Base):
    __tablename__ = "config"

    key = Column(Text, primary_key=True)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(Text, nullable=False, default=_now)
```

- [ ] **Step 7: 安装依赖并验证数据库初始化**

```bash
cd /media/cvitek/martin.xuan/dianshang
pip install -r requirements.txt
python -c "
import asyncio
from database import init_db
asyncio.run(init_db())
print('Database initialized successfully')
"
```

- [ ] **Step 8: Commit**

```bash
git add requirements.txt .env.example .gitignore settings.py database.py models.py
git commit -m "feat: project skeleton with settings, database, and models"
```

---

### Task 2: SophNet HTTP 客户端

**Files:**
- Create: `services/__init__.py`
- Create: `services/sophnet_client.py`

**Interfaces:**
- Consumes: `settings.SETTINGS` (api_key, llm_base_url, video_gen_url, video_query_url, timeouts, retry counts)
- Produces: `SophNetClient`
  - `async chat_completion(model: str, messages: list[dict], temperature: float = 0.7) -> dict`
  - `async generate_video(model: str, content: list[dict], parameters: dict) -> dict`
  - `async query_video_task(task_id: str) -> dict`
  - `async download_file(url: str, dest_path: str) -> None`

- [ ] **Step 1: 创建 services/__init__.py**

```python
```

- [ ] **Step 2: 创建 services/sophnet_client.py**

```python
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
        """Query the status of a video generation task."""
        client = await self._get_client()
        resp = await client.get(
            SETTINGS.video_query_url, params={"task_id": task_id}
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
```

- [ ] **Step 3: 验证客户端可以初始化**

```bash
cd /media/cvitek/martin.xuan/dianshang
python -c "
from services.sophnet_client import SophNetClient
c = SophNetClient(api_key='test')
print('SophNetClient created successfully')
print(f'LLM URL: {c._client is None}')
"
```

- [ ] **Step 4: Commit**

```bash
git add services/__init__.py services/sophnet_client.py
git commit -m "feat: SophNet HTTP client with retry for LLM and video generation"
```

---

### Task 3: LLM 服务 — Prompt 链与调用

**Files:**
- Create: `services/llm_service.py`

**Interfaces:**
- Consumes: `services.sophnet_client.SophNetClient` (chat_completion)
- Consumes: `settings.SETTINGS`
- Produces:
  - `async analyze_image(client: SophNetClient, model: str, image_base64: str) -> dict`
  - `async generate_promo_texts(client: SophNetClient, model: str, image_analysis: dict, specs: dict) -> dict`
  - `async generate_storyboard(client: SophNetClient, model: str, product_info: str, promo_texts: dict) -> list[dict]`

- [ ] **Step 1: 创建 services/llm_service.py**

```python
import json
import re
from services.sophnet_client import SophNetClient


def _extract_json(text: str) -> dict | list:
    """Extract JSON object or array from LLM response that may contain markdown fences."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from ```json ... ``` block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return json.loads(match.group(1))
    # Try finding first { or [
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == start_char:
                depth += 1
            elif c == end_char:
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
    raise ValueError(f"Could not extract JSON from response: {text[:200]}...")


ANALYZE_IMAGE_PROMPT = """你是一个电商产品分析专家。请分析以下产品图片，严格输出 JSON（不要包含其他内容）：

{
  "category": "产品品类",
  "material": "材质",
  "style": "风格",
  "color_scheme": "配色方案",
  "target_audience": "目标人群",
  "key_features": ["卖点1", "卖点2", "卖点3"],
  "visual_highlights": "视觉亮点描述",
  "suggested_shooting_style": "建议拍摄风格"
}"""


async def analyze_image(client: SophNetClient, model: str, image_base64: str) -> dict:
    """Analyze product image using a vision-capable model."""
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
            {"type": "text", "text": ANALYZE_IMAGE_PROMPT},
        ],
    }]
    result = await client.chat_completion(model, messages, temperature=0.7)
    return _extract_json(result["content"])


PROMO_TEXT_PROMPT = """你是一个顶级的电商文案策划。根据以下产品分析结果和规格参数，生成淘宝店铺的宣传内容。

产品分析：{image_analysis}
产品规格：{specs}

请严格输出 JSON（不要包含其他内容）：
{
  "title": "吸引人的商品标题（含核心卖点关键词，30字以内）",
  "short_description": "一句话卖点描述",
  "selling_points": ["卖点详情1", "卖点详情2", "卖点详情3"],
  "promotional_prompt": "用于AI生图的提示词（中英双语，详细描述产品拍摄场景、光线、构图）",
  "marketing_copy": "完整的详情页营销文案（200-300字）"
}"""


async def generate_promo_texts(
    client: SophNetClient, model: str, image_analysis: dict, specs: dict
) -> dict:
    """Generate promotional copy based on image analysis and user specs."""
    prompt = PROMO_TEXT_PROMPT.format(
        image_analysis=json.dumps(image_analysis, ensure_ascii=False),
        specs=json.dumps(specs, ensure_ascii=False),
    )
    messages = [{"role": "user", "content": prompt}]
    result = await client.chat_completion(model, messages, temperature=0.8)
    return _extract_json(result["content"])


STORYBOARD_PROMPT = """你是一个专业的广告导演。基于以下产品信息和宣传文案，设计一个 15 秒的商品展示视频分镜头脚本。

产品信息：{product_info}
宣传文案：{promo_texts}

请输出 5-8 个分镜头的 JSON 数组（不要包含其他内容）：
[
  {
    "shot_number": 1,
    "duration_sec": 3,
    "scene_description": "中文场景描述（构图、主体、背景、氛围）",
    "camera_movement": "运镜方式（推/拉/摇/移/固定等）",
    "cn_prompt": "适合视频生成模型的中文提示词",
    "en_prompt": "English prompt suitable for AI video generation (detailed, visual, include motion description)",
    "narration": "该镜头的配音/旁白文本"
  }
]

要求：
- 整体节奏流畅，适合商品展示
- 每个分镜头的 en_prompt 要具体、可视化，包含动作描述
- 考虑视频模型的提示词最佳实践
- 直接输出 JSON 数组，不要添加任何额外文字说明"""


async def generate_storyboard(
    client: SophNetClient, model: str, product_info: str, promo_texts: dict
) -> list[dict]:
    """Generate video storyboard / shot list."""
    prompt = STORYBOARD_PROMPT.format(
        product_info=product_info,
        promo_texts=json.dumps(promo_texts, ensure_ascii=False),
    )
    messages = [{"role": "user", "content": prompt}]
    result = await client.chat_completion(model, messages, temperature=0.9)
    return _extract_json(result["content"])
```

- [ ] **Step 2: 验证模块可导入且 Prompt 格式正确**

```bash
cd /media/cvitek/martin.xuan/dianshang
python -c "
from services.llm_service import _extract_json, ANALYZE_IMAGE_PROMPT, PROMO_TEXT_PROMPT, STORYBOARD_PROMPT
# Test JSON extraction
result = _extract_json('{\"a\": 1}')
assert result == {'a': 1}, f'Got {result}'
result2 = _extract_json('```json\n{\"b\": 2}\n```')
assert result2 == {'b': 2}, f'Got {result2}'
result3 = _extract_json('some text [{\"c\": 3}] more text')
assert result3 == [{'c': 3}], f'Got {result3}'
print('All extraction tests passed')
print('Prompt templates loaded successfully')
"
```

- [ ] **Step 3: Commit**

```bash
git add services/llm_service.py
git commit -m "feat: LLM service with image analysis, promo text, and storyboard generation"
```

---

### Task 4: 视频服务 — 生成提交与轮询

**Files:**
- Create: `services/video_service.py`

**Interfaces:**
- Consumes: `services.sophnet_client.SophNetClient` (generate_video, query_video_task, download_file)
- Consumes: `settings.SETTINGS`
- Consumes: `models.VideoTask`
- Produces:
  - `async submit_video_generation(client: SophNetClient, model: str, image_path: str, prompt_text: str, duration: int = 5, resolution: str = "720P") -> dict`
  - `async poll_video_task(client: SophNetClient, sophnet_task_id: str) -> str` (returns video_url)
  - `async generate_and_download(client: SophNetClient, video_task: VideoTask, model: str, duration: int = 5, resolution: str = "720P", on_update: callable | None = None) -> str`

- [ ] **Step 1: 创建 services/video_service.py**

```python
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
    # Detect mime type from extension
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

        # Update callback for status tracking
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
    # Submit
    submit_result = await submit_video_generation(
        client, model, video_task.input_image, video_task.prompt, duration, resolution
    )
    # Extract task_id — adapt to actual SophNet response
    sophnet_task_id = submit_result.get("task_id") or submit_result.get("data", {}).get("task_id")
    if not sophnet_task_id:
        # Try snake_case keys
        sophnet_task_id = (
            submit_result.get("data", {}).get("task_id")
            or submit_result.get("taskId")
        )
    if not sophnet_task_id:
        raise SophNetError(f"Cannot extract task_id from response: {submit_result}")

    video_task.sophnet_task_id = sophnet_task_id

    # Poll
    video_url = await poll_video_task(client, sophnet_task_id, on_update=on_update)

    # Download
    task_dir = os.path.join(SETTINGS.output_dir, video_task.task_id)
    os.makedirs(task_dir, exist_ok=True)
    ext = ".mp4"
    local_path = os.path.join(task_dir, f"shot_{video_task.shot_index}{ext}")
    await client.download_file(video_url, local_path)

    return local_path
```

- [ ] **Step 2: 验证模块可导入**

```bash
cd /media/cvitek/martin.xuan/dianshang
python -c "
from services.video_service import _image_to_data_url, VideoTimeoutError
print('Video service module loaded successfully')
"
```

- [ ] **Step 3: Commit**

```bash
git add services/video_service.py
git commit -m "feat: video generation service with submit, poll, and download pipeline"
```

---

### Task 5: 工作流编排器

**Files:**
- Create: `services/workflow.py`

**Interfaces:**
- Consumes: `services.sophnet_client.SophNetClient`
- Consumes: `services.llm_service` (analyze_image, generate_promo_texts, generate_storyboard)
- Consumes: `services.video_service` (generate_and_download)
- Consumes: `database.get_db`, `models.Task`, `models.VideoTask`
- Consumes: `settings.SETTINGS`
- Produces: `async execute_workflow(task_id: str) -> None`

- [ ] **Step 1: 创建 services/workflow.py**

```python
import asyncio
import base64
import json
import os
import traceback
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from models import Task, VideoTask
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
            # Merge extra fields into result
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
    client = SophNetClient()
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

            # Load video_task from db
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

            # Persist video task update
            async with async_session() as db:
                vt_db = await db.get(VideoTask, vt.id)
                if vt_db:
                    vt_db.status = vt.status
                    vt_db.video_path = vt.video_path
                    vt_db.sophnet_task_id = vt.sophnet_task_id
                    vt_db.updated_at = vt.updated_at
                    await db.commit()

        # Mark complete
        await _update_task_status(task_id, "completed", videos=videos_result)

    except Exception as e:
        error_detail = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        await _update_task_error(task_id, error_detail)
    finally:
        await client.close()
```

- [ ] **Step 2: 验证模块语法正确**

```bash
cd /media/cvitek/martin.xuan/dianshang
python -c "
from services.workflow import execute_workflow, _update_task_status, _now
print('Workflow module loaded successfully')
"
```

- [ ] **Step 3: Commit**

```bash
git add services/workflow.py
git commit -m "feat: workflow orchestrator with 4-stage pipeline"
```

---

### Task 6: API 路由 — 任务管理

**Files:**
- Create: `routers/__init__.py`
- Create: `routers/tasks.py`

**Interfaces:**
- Consumes: `database.get_db`, `models.Task`, `models.VideoTask`
- Consumes: `services.workflow.execute_workflow`
- Produces: FastAPI APIRouter with routes:
  - `POST /api/tasks` — 创建任务
  - `GET /api/tasks` — 任务列表
  - `GET /api/tasks/{id}` — 任务详情
  - `DELETE /api/tasks/{id}` — 删除任务
  - `POST /api/tasks/{id}/retry` — 重试
  - `GET /api/tasks/{id}/videos/{shot_index}` — 下载视频

- [ ] **Step 1: 创建 routers/__init__.py**

```python
```

- [ ] **Step 2: 创建 routers/tasks.py**

```python
import asyncio
import json
import os
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Task, VideoTask
from services.workflow import execute_workflow
from settings import SETTINGS

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("")
async def create_task(
    images: list[UploadFile] = File(...),
    specs: str = Form(...),
    llm_model: str = Form(default=SETTINGS.preferred_llm_model),
    video_model: str = Form(default=SETTINGS.preferred_video_model),
    db: AsyncSession = Depends(get_db),
):
    """Create a new task: upload images + specs, trigger async workflow."""
    # Check image size
    for img in images:
        contents = await img.read()
        if len(contents) > SETTINGS.max_image_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"Image {img.filename} exceeds {SETTINGS.max_image_size_mb}MB limit",
            )
        await img.seek(0)

    # Save images
    task = Task(
        llm_model=llm_model,
        video_model=video_model,
        specs=specs,
    )
    db.add(task)
    await db.flush()  # Get task.id

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

    # Launch async workflow
    asyncio.create_task(execute_workflow(task.id))

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

    # Count total
    count_stmt = select(func.count()).select_from(Task)
    if status:
        count_stmt = count_stmt.where(Task.status == status)
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginate
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

    # Get video sub-tasks
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

    # Delete files
    upload_dir = os.path.join(SETTINGS.upload_dir, task_id)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)
    output_dir = os.path.join(SETTINGS.output_dir, task_id)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    # Delete video sub-tasks
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
    task.updated_at = Task.created_at.default.arg if callable(Task.created_at.default.arg) else ""
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
```

- [ ] **Step 3: 验证路由模块可导入**

```bash
cd /media/cvitek/martin.xuan/dianshang
python -c "
from routers.tasks import router
print('Tasks router loaded successfully')
print('Routes:', [r.path for r in router.routes])
"
```

- [ ] **Step 4: Commit**

```bash
git add routers/__init__.py routers/tasks.py
git commit -m "feat: task CRUD API routes with file upload and video download"
```

---

### Task 7: API 路由 — 配置管理

**Files:**
- Create: `routers/config.py`

**Interfaces:**
- Consumes: `database.get_db`, `models.Config`
- Produces: FastAPI APIRouter with routes:
  - `GET /api/config`
  - `POST /api/config`

- [ ] **Step 1: 创建 routers/config.py**

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Config

router = APIRouter(prefix="/api/config", tags=["config"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConfigUpdate(BaseModel):
    key: str
    value: str


@router.get("")
async def get_config(db: AsyncSession = Depends(get_db)):
    """Get all configuration key-value pairs."""
    from sqlalchemy import select
    result = await db.execute(select(Config))
    configs = result.scalars().all()
    return {c.key: c.value for c in configs}


@router.post("")
async def set_config(body: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    """Set a configuration value."""
    from sqlalchemy import select

    result = await db.execute(select(Config).where(Config.key == body.key))
    config = result.scalar_one_or_none()

    if config:
        config.value = body.value
        config.updated_at = _now()
    else:
        config = Config(key=body.key, value=body.value, updated_at=_now())
        db.add(config)

    await db.commit()
    return {"key": body.key, "value": body.value}
```

- [ ] **Step 2: 验证模块可导入**

```bash
cd /media/cvitek/martin.xuan/dianshang
python -c "
from routers.config import router
print('Config router loaded successfully')
"
```

- [ ] **Step 3: Commit**

```bash
git add routers/config.py
git commit -m "feat: config management API for storing API key and preferences"
```

---

### Task 8: 前端页面路由

**Files:**
- Create: `routers/pages.py`

**Interfaces:**
- Consumes: `database.get_db`, `models.Task`, `models.VideoTask`
- Produces: FastAPI APIRouter with page routes returning Jinja2 templates

- [ ] **Step 1: 创建 routers/pages.py**

```python
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Task, VideoTask
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
    return request.app.state.templates.TemplateResponse("tasks.html", {
        "request": request,
    })


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
async def page_settings(request: Request):
    return request.app.state.templates.TemplateResponse("settings.html", {
        "request": request,
        "llm_models": [
            "DeepSeek-V4-Flash-Vision-Exp",
            "glm-4-flash",
            "kimi",
        ],
        "video_models": [
            "wan2.7",
            "happyhorse-1.1-i2v",
        ],
    })
```

- [ ] **Step 2: Commit**

```bash
git add routers/pages.py
git commit -m "feat: page routes for index, tasks, task detail, and settings"
```

---

### Task 9: Jinja2 模板

**Files:**
- Create: `templates/base.html`
- Create: `templates/index.html`
- Create: `templates/tasks.html`
- Create: `templates/task_detail.html`
- Create: `templates/settings.html`

**Interfaces:**
- Consumes: `routers.pages` 传递的 context 变量

- [ ] **Step 1: 创建 templates/base.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>电商AI内容生产工具</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <nav class="container-fluid">
        <ul>
            <li><strong>📦 电商AI工具</strong></li>
            <li><a href="/">新建任务</a></li>
            <li><a href="/tasks">任务列表</a></li>
            <li><a href="/settings">设置</a></li>
        </ul>
    </nav>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

- [ ] **Step 2: 创建 templates/index.html**

```html
{% extends "base.html" %}
{% block content %}
<h2>创建新任务</h2>
<form id="create-form"
      hx-post="/api/tasks"
      hx-encoding="multipart/form-data"
      hx-target="#result"
      hx-swap="innerHTML">

    <label>产品图片（可多选）
        <input type="file" name="images" accept="image/*" multiple required>
    </label>

    <fieldset>
        <legend>产品规格</legend>
        <div id="specs-container">
            <div class="grid spec-row">
                <input type="text" name="spec_key_0" placeholder="规格名（如：品类）" value="品类">
                <input type="text" name="spec_value_0" placeholder="规格值（如：女装连衣裙）">
            </div>
            <div class="grid spec-row">
                <input type="text" name="spec_key_1" placeholder="规格名" value="材质">
                <input type="text" name="spec_value_1" placeholder="规格值">
            </div>
            <div class="grid spec-row">
                <input type="text" name="spec_key_2" placeholder="规格名" value="风格">
                <input type="text" name="spec_value_2" placeholder="规格值">
            </div>
            <div class="grid spec-row">
                <input type="text" name="spec_key_3" placeholder="规格名" value="目标人群">
                <input type="text" name="spec_value_3" placeholder="规格值">
            </div>
            <div class="grid spec-row">
                <input type="text" name="spec_key_4" placeholder="规格名">
                <input type="text" name="spec_value_4" placeholder="规格值">
            </div>
        </div>
        <button type="button" class="secondary outline" onclick="addSpecRow()" style="margin-top:0.5rem">
            + 添加规格
        </button>
    </fieldset>

    <div class="grid">
        <label>LLM 模型
            <select name="llm_model">
                <option value="DeepSeek-V4-Flash-Vision-Exp">DeepSeek-V4-Flash-Vision-Exp</option>
                <option value="glm-4-flash">GLM-4-Flash</option>
                <option value="kimi">Kimi</option>
            </select>
        </label>
        <label>视频模型
            <select name="video_model">
                <option value="happyhorse-1.1-i2v">HappyHorse-1.1-i2v</option>
                <option value="wan2.7">WAN 2.7</option>
            </select>
        </label>
    </div>

    <input type="hidden" name="specs" id="specs-json">

    <button type="submit" onclick="prepareSpecs()">🚀 开始生成</button>
</form>

<div id="result"></div>

<script>
let specCounter = 5;
function addSpecRow() {
    const container = document.getElementById('specs-container');
    const row = document.createElement('div');
    row.className = 'grid spec-row';
    row.innerHTML = `
        <input type="text" name="spec_key_${specCounter}" placeholder="规格名">
        <input type="text" name="spec_value_${specCounter}" placeholder="规格值">
    `;
    container.appendChild(row);
    specCounter++;
}
function prepareSpecs() {
    const rows = document.querySelectorAll('.spec-row');
    const specs = {};
    rows.forEach(row => {
        const keyInput = row.querySelector('input[name^="spec_key_"]');
        const valInput = row.querySelector('input[name^="spec_value_"]');
        if (keyInput && valInput && keyInput.value.trim()) {
            specs[keyInput.value.trim()] = valInput.value.trim();
        }
    });
    document.getElementById('specs-json').value = JSON.stringify(specs);
}
</script>
{% endblock %}
```

- [ ] **Step 3: 创建 templates/tasks.html**

```html
{% extends "base.html" %}
{% block content %}
<h2>任务列表</h2>

<div class="grid">
    <div>
        <label>状态筛选
            <select name="status_filter"
                    hx-get="/api/tasks"
                    hx-target="#task-table-body"
                    hx-trigger="change"
                    hx-include="this">
                <option value="">全部</option>
                <option value="pending">待处理</option>
                <option value="analyzing">分析中</option>
                <option value="writing">生成文案</option>
                <option value="storyboard">分镜头脚本</option>
                <option value="generating_video">生成视频</option>
                <option value="completed">已完成</option>
                <option value="failed">失败</option>
            </select>
        </label>
    </div>
    <div style="text-align:right">
        <button class="secondary" hx-get="/api/tasks" hx-target="#task-table-body">
            🔄 刷新
        </button>
    </div>
</div>

<table>
    <thead>
        <tr>
            <th>缩略图</th>
            <th>规格</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>操作</th>
        </tr>
    </thead>
    <tbody id="task-table-body"
           hx-get="/api/tasks"
           hx-trigger="load"
           hx-swap="innerHTML">
        <tr><td colspan="5" aria-busy="true">加载中...</td></tr>
    </tbody>
</table>

<div id="pagination"></div>
{% endblock %}
```

- [ ] **Step 4: 创建 templates/task_detail.html**

```html
{% extends "base.html" %}
{% block content %}
{% set status = task.status %}
{% set result = task.result %}
{% set is_done = status in ('completed', 'failed') %}

<h2>任务详情</h2>

<!-- Progress bar -->
<progress value="{{ {'pending':5,'analyzing':25,'writing':40,'storyboard':60,'generating_video':80,'completed':100,'failed':100}.get(status, 5) }}" max="100"></progress>
<p>
    <strong>状态：</strong>
    {% set labels = {'pending':'⏳ 等待中','analyzing':'🔍 分析图片','writing':'✍️ 生成文案','storyboard':'🎬 分镜头脚本','generating_video':'🎥 生成视频','completed':'✅ 完成','failed':'❌ 失败'} %}
    {{ labels.get(status, status) }}
    <small>| 模型：{{ task.llm_model }} / {{ task.video_model }}</small>
    <small>| 创建时间：{{ task.created_at[:19] }}</small>
</p>

{% if status == 'failed' %}
<article style="background:var(--pico-color-red-50);border:1px solid var(--pico-color-red-200)">
    <h4>❌ 任务失败</h4>
    <pre style="white-space:pre-wrap;font-size:0.85rem">{{ task.error_message }}</pre>
    <button hx-post="/api/tasks/{{ task.id }}/retry" hx-target="body" hx-swap="outerHTML">
        🔄 重试任务
    </button>
</article>
{% endif %}

<!-- Stage cards -->
{% if result.image_analysis %}
<article>
    <h3>🔍 图片分析</h3>
    <div class="grid">
        {% for path in task.image_paths %}
        <img src="/{{ path }}" alt="产品图" style="max-width:200px;border-radius:8px">
        {% endfor %}
    </div>
    <dl>
        {% for k, v in result.image_analysis.items() %}
        {% if v is string %}
        <dt><strong>{{ k }}</strong></dt><dd>{{ v }}</dd>
        {% elif v is iterable and v is not mapping %}
        <dt><strong>{{ k }}</strong></dt><dd>{{ v | join('、') }}</dd>
        {% endif %}
        {% endfor %}
    </dl>
</article>
{% endif %}

{% if result.promo_texts %}
<article>
    <h3>✍️ 宣传文案</h3>
    {% set pt = result.promo_texts %}
    <h4>{{ pt.title }}</h4>
    <p><em>{{ pt.short_description }}</em></p>
    <h5>卖点</h5>
    <ul>
        {% for sp in pt.selling_points %}
        <li>{{ sp }}</li>
        {% endfor %}
    </ul>
    <h5>营销提示词</h5>
    <pre style="white-space:pre-wrap">{{ pt.promotional_prompt }}</pre>
    <h5>营销文案</h5>
    <pre style="white-space:pre-wrap">{{ pt.marketing_copy }}</pre>
</article>
{% endif %}

{% if result.storyboard %}
<article>
    <h3>🎬 分镜头脚本</h3>
    {% for shot in result.storyboard %}
    <details {% if loop.index == 1 %}open{% endif %}>
        <summary>第 {{ shot.shot_number }} 镜 — {{ shot.duration_sec }}s</summary>
        <dl>
            <dt><strong>场景描述</strong></dt><dd>{{ shot.scene_description }}</dd>
            <dt><strong>运镜方式</strong></dt><dd>{{ shot.camera_movement }}</dd>
            <dt><strong>中文提示词</strong></dt><dd>{{ shot.cn_prompt }}</dd>
            <dt><strong>英文提示词</strong></dt><dd>{{ shot.en_prompt }}</dd>
            <dt><strong>旁白</strong></dt><dd>{{ shot.narration }}</dd>
        </dl>
    </details>
    {% endfor %}
</article>
{% endif %}

{% if result.videos %}
<article>
    <h3>🎥 生成视频</h3>
    <div class="grid">
    {% for v in result.videos %}
        <div>
            <h4>分镜头 {{ v.shot_index + 1 }}</h4>
            {% if v.status == 'completed' and v.path %}
            <video controls width="100%" style="max-width:400px;border-radius:8px">
                <source src="/{{ v.path }}" type="video/mp4">
            </video>
            <p><a href="/api/tasks/{{ task.id }}/videos/{{ v.shot_index }}" download>⬇ 下载</a></p>
            {% else %}
            <p>❌ 生成失败：{{ v.get('error', '未知错误') }}</p>
            {% endif %}
        </div>
    {% endfor %}
    </div>
</article>
{% endif %}

{% if not is_done %}
<div id="auto-refresh"
     hx-get="/tasks/{{ task.id }}"
     hx-trigger="every 3s"
     hx-target="body"
     hx-swap="outerHTML"
     hx-select="body">
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 5: 创建 templates/settings.html**

```html
{% extends "base.html" %}
{% block content %}
<h2>设置</h2>

<form hx-post="/api/config" hx-target="#config-result" hx-swap="innerHTML">
    <label>SophNet API Key
        <input type="password" name="key" value="api_key" readonly>
        <input type="password" name="value" placeholder="输入 API Key" required>
    </label>
    <button type="submit">💾 保存 API Key</button>
</form>

<form hx-post="/api/config" hx-target="#config-result" hx-swap="innerHTML" style="margin-top:1rem">
    <label>默认 LLM 模型
        <select name="key">
            <option value="preferred_llm_model" selected>preferred_llm_model</option>
        </select>
        <select name="value">
            {% for m in llm_models %}
            <option value="{{ m }}">{{ m }}</option>
            {% endfor %}
        </select>
    </label>
    <button type="submit">💾 保存</button>
</form>

<form hx-post="/api/config" hx-target="#config-result" hx-swap="innerHTML" style="margin-top:1rem">
    <label>默认视频模型
        <select name="key">
            <option value="preferred_video_model" selected>preferred_video_model</option>
        </select>
        <select name="value">
            {% for m in video_models %}
            <option value="{{ m }}">{{ m }}</option>
            {% endfor %}
        </select>
    </label>
    <button type="submit">💾 保存</button>
</form>

<div id="config-result"></div>

<hr>
<h3>当前配置</h3>
<div hx-get="/api/config" hx-trigger="load" hx-swap="innerHTML">
    <p aria-busy="true">加载中...</p>
</div>
{% endblock %}
```

- [ ] **Step 6: 创建 static/style.css**

```css
/* Custom styles for the e-commerce AI tool */
.spec-row {
    margin-bottom: 0.5rem;
}
.spec-row input {
    margin-bottom: 0;
}
#result {
    margin-top: 1rem;
}
video {
    background: #000;
}
article h3 {
    margin-bottom: 0.5rem;
}
nav {
    border-bottom: 1px solid var(--pico-color-grey-100);
    margin-bottom: 1rem;
}
```

- [ ] **Step 7: 验证模板语法**

```bash
cd /media/cvitek/martin.xuan/dianshang
python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates'))
for name in ['base.html', 'index.html', 'tasks.html', 'task_detail.html', 'settings.html']:
    tpl = env.get_template(name)
    print(f'{name}: OK')
"
```

- [ ] **Step 8: Commit**

```bash
git add templates/ static/ routers/pages.py
git commit -m "feat: Jinja2 templates with HTMX and Pico.css for all pages"
```

---

### Task 10: 应用入口 — app.py

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: all routers, database.init_db, settings
- Produces: Runnable FastAPI application

- [ ] **Step 1: 创建 app.py**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from database import init_db
from routers.config import router as config_router
from routers.pages import router as pages_router
from routers.tasks import router as tasks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Setup Jinja2
    env = Environment(loader=FileSystemLoader("templates"))
    app.state.templates = env
    yield


app = FastAPI(title="电商AI内容生产工具", lifespan=lifespan)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# Routers
app.include_router(pages_router)
app.include_router(tasks_router)
app.include_router(config_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
```

- [ ] **Step 2: 启动应用验证可运行**

```bash
cd /media/cvitek/martin.xuan/dianshang
python app.py &
sleep 3
# Test the index page
curl -s http://localhost:8080/ | head -5
# Kill the server
kill %1 2>/dev/null
```

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: FastAPI application entry point with lifespan and static mounts"
```

---

### Task 11: 任务列表 API 响应适配 HTMX 表格渲染

**Files:**
- Modify: `routers/tasks.py` — 添加 HTML 片段路由
- Create: `templates/_task_rows.html`

**Interfaces:**
- Consumes: `models.Task`
- Produces: `GET /api/tasks?format=html` 返回 `<tr>` HTML 片段

- [ ] **Step 1: 创建 templates/_task_rows.html**

```html
{% for t in tasks %}
<tr>
    <td>
        {% set paths = t.image_paths %}
        {% if paths and paths[0] %}
        <img src="/{{ paths[0] }}" alt="缩略图" style="width:60px;height:60px;object-fit:cover;border-radius:4px">
        {% else %}
        <span>无图片</span>
        {% endif %}
    </td>
    <td>
        {% set specs = t.specs %}
        <small>{{ specs.get('品类', '') or specs.values()|first or '-' }}</small>
    </td>
    <td>
        {% set labels = {'pending':'⏳ 等待','analyzing':'🔍 分析','writing':'✍️ 文案','storyboard':'🎬 脚本','generating_video':'🎥 视频','completed':'✅ 完成','failed':'❌ 失败'} %}
        <span>{{ labels.get(t.status, t.status) }}</span>
    </td>
    <td><small>{{ t.created_at[:19] }}</small></td>
    <td>
        <a href="/tasks/{{ t.id }}" role="button" class="secondary small">查看</a>
        <button class="secondary small"
                hx-delete="/api/tasks/{{ t.id }}"
                hx-target="closest tr"
                hx-swap="delete"
                hx-confirm="确认删除？">
            🗑
        </button>
    </td>
</tr>
{% endfor %}
{% if not tasks %}
<tr><td colspan="5" style="text-align:center">暂无任务</td></tr>
{% endif %}
```

- [ ] **Step 2: 在 routers/tasks.py 的 list_tasks 中添加 HTML 格式支持**

在 `list_tasks` 函数`return`之前加入：

```python
# Check if client wants HTML partial (HTMX table rows)
    from fastapi import Request as FastAPIRequest
```

实际上这需要在函数签名里加 `Request`。让我调整策略——直接在 task list API 的 return 前检测 query param `format=html`，然后返回 Jinja2 渲染的片段。

更简洁的做法：修改 `list_tasks` 函数，增加 `request: Request` 参数和 HTML 返回。

但在 routers/tasks.py 中我们没有直接访问 templates 的途径。更好的做法是：在 `pages.py` 中新增一个专门的 HTML 片段路由。

新增路由到 routers/pages.py：

```python
@router.get("/api/tasks-rows", response_class=HTMLResponse)
async def page_task_rows(request: Request, status: str | None = None, db: AsyncSession = Depends(get_db)):
    # ...same query logic, return _task_rows.html
```

然后 templates/tasks.html 中 `hx-get` 改为 `/api/tasks-rows`。

这样更清晰。让我重写这个子任务。

- [ ] **Step 1: 在 routers/pages.py 末尾新增任务行 HTML 片段路由**

```python
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
```

- [ ] **Step 2: 更新 templates/tasks.html 中的 hx-get 地址**

把 `hx-get="/api/tasks"` 改为 `hx-get="/api/tasks-rows"`（在 tbody 上）

- [ ] **Step 3: 更新 templates/tasks.html 中筛选下拉框和刷新按钮的 hx-get**

```html
<select name="status_filter"
        hx-get="/api/tasks-rows"
        hx-target="#task-table-body"
        hx-trigger="change"
        hx-include="this">
```

```html
<button class="secondary" hx-get="/api/tasks-rows" hx-target="#task-table-body">
    🔄 刷新
</button>
```

- [ ] **Step 4: 验证模板片段渲染正确**

```bash
cd /media/cvitek/martin.xuan/dianshang
python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates'))
tpl = env.get_template('_task_rows.html')
print('_task_rows.html: OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add templates/_task_rows.html routers/pages.py templates/tasks.html
git commit -m "feat: HTMX task row partial rendering for live table updates"
```

---

### Task 12: 完善 & README

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建 README.md**

```markdown
# 电商AI内容生产工具

输入产品图片和规格，自动生成宣传文案、分镜头脚本和AI宣传视频。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入 SophNet API Key
```

或启动后在设置页面（/settings）中配置。

### 3. 启动

```bash
python app.py
```

访问 http://localhost:8080

## 功能

- 📸 **图片分析**: 上传产品图，Vision 模型自动识别品类、材质、风格
- ✍️ **文案生成**: 自动生成商品标题、卖点描述、营销提示词、详情页文案
- 🎬 **分镜头脚本**: 生成 5-8 个分镜头，含运镜描述和中英文视频 prompt
- 🎥 **视频生成**: 调用 WAN2.7 / HappyHorse 生成宣传视频片段

## 支持的模型

| 类型 | 模型 |
|------|------|
| LLM (视觉) | DeepSeek-V4-Flash-Vision-Exp |
| LLM (文本) | GLM-4-Flash, Kimi |
| 视频生成 | WAN 2.7, HappyHorse-1.1-i2v |

## 技术栈

- FastAPI + Jinja2 + HTMX + Pico.css
- SQLite + SQLAlchemy (async)
- SophNet 算力平台 API

## 目录结构

```
dianshang/
├── app.py              # 入口
├── settings.py         # 配置
├── models.py           # 数据模型
├── database.py         # 数据库
├── routers/            # API + 页面路由
├── services/           # 核心服务
├── templates/          # Jinja2 模板
├── static/             # 静态资源
├── uploads/            # 上传图片
└── outputs/            # 生成视频
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with quick start and feature overview"
```

---

### Task 13: 端到端集成测试 & 修复

- [ ] **Step 1: 确保所有模块可正常导入**

```bash
cd /media/cvitek/martin.xuan/dianshang
python -c "
from app import app
print('App loaded successfully')
print('Routes:')
for route in app.routes:
    if hasattr(route, 'path'):
        print(f'  {route.path}')
"
```

- [ ] **Step 2: 检查 templates/task_detail.html 中 Jinja2 兼容性**

```bash
cd /media/cvitek/martin.xuan/dianshang
python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates'))
# Render with dummy context
ctx = {
    'task': {
        'id': 'test123', 'status': 'completed',
        'image_paths': [], 'specs': {}, 'llm_model': 'test', 'video_model': 'test',
        'result': {
            'image_analysis': {'category': 'test'},
            'promo_texts': {'title': 'test', 'short_description': 'test', 'selling_points': [], 'promotional_prompt': 'test', 'marketing_copy': 'test'},
            'storyboard': [{'shot_number': 1, 'duration_sec': 3, 'scene_description': 'test', 'camera_movement': 'test', 'cn_prompt': 'test', 'en_prompt': 'test', 'narration': 'test'}],
            'videos': [{'shot_index': 0, 'path': 'test.mp4', 'status': 'completed'}]
        },
        'error_message': None, 'created_at': '2026-11-08T00:00:00'
    },
    'video_tasks': [],
    'request': type('obj', (object,), {'url': type('obj', (object,), {'path': '/tasks/test123'})()}),
}
tpl = env.get_template('task_detail.html')
output = tpl.render(ctx)
print(f'Rendered {len(output)} chars OK')
"
```

- [ ] **Step 3: 修复 task_detail.html 中的 iterable 检测问题**

Jinja2 的 `is iterable` 对 string 也会返回 True，需要修复模板中 `result.image_analysis` 的遍历逻辑。

修改 `templates/task_detail.html` 中的图片分析展示部分：

```jinja2
{% if result.image_analysis %}
<article>
    <h3>🔍 图片分析</h3>
    <div class="grid">
        {% for path in task.image_paths %}
        <img src="/{{ path }}" alt="产品图" style="max-width:200px;border-radius:8px">
        {% endfor %}
    </div>
    <table>
        {% for k, v in result.image_analysis.items() %}
        <tr>
            <th>{{ k }}</th>
            <td>
                {% if v is not string and v is iterable %}
                    {{ v | join('、') }}
                {% else %}
                    {{ v }}
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </table>
</article>
{% endif %}
```

- [ ] **Step 4: 启动并测试基本功能**

```bash
cd /media/cvitek/martin.xuan/dianshang
python app.py &
sleep 3
# Test health
curl -s http://localhost:8080/ | grep -o '<title>.*</title>'
echo "---"
# Test config API
curl -s http://localhost:8080/api/config
echo "---"
# Test tasks list
curl -s http://localhost:8080/api/tasks | python -m json.tool | head -10
kill %1 2>/dev/null
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "fix: Jinja2 template compatibility fixes and end-to-end verification"
```