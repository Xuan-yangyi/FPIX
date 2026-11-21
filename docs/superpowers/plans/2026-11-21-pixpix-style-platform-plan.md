# PixPix-Style E-Commerce AI Image Platform — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the existing dianshang project from a single-purpose video generation tool into a PixPix-style multi-tool AI e-commerce image platform with 5 workflows (product_set, remove_bg, model, video, edit) and a modern React SPA frontend.

**Architecture:** FastAPI backend serves REST + SSE APIs; React SPA (Vite + Tailwind + shadcn/ui + Framer Motion) replaces Jinja2/HTMX templates. Single-process deployment — FastAPI mounts the built React static files. Backend orchestrates multi-stage workflows: LLM analysis → prompt engineering → image/video generation via SophNet.

**Tech Stack:** Python FastAPI, SQLAlchemy async, React 18 TypeScript, Vite, Tailwind CSS 4, shadcn/ui, Framer Motion, React Router v6

**Spec:** `docs/superpowers/specs/2026-11-21-pixpix-style-platform-design.md`

## Global Constraints

- Single-process deployment: FastAPI serves both API and built SPA static files
- All AI calls go through SophNet API gateway
- SSE used for real-time progress (not WebSocket)
- Dark theme matching PixPix visual style (#0a0a0f background, #6366f1 accent)
- Workflow orchestration is code-based (Python), not LLM Agent-based
- Task model extended with `workflow_type` and `params` (JSON) fields
- Existing video workflow and SophNet client patterns must be preserved

---

## File Map

```
Files to CREATE:
  frontend/package.json
  frontend/tsconfig.json
  frontend/vite.config.ts
  frontend/tailwind.config.ts
  frontend/index.html
  frontend/src/main.tsx
  frontend/src/App.tsx
  frontend/src/index.css
  frontend/src/lib/utils.ts
  frontend/src/types/index.ts
  frontend/src/api/client.ts
  frontend/src/hooks/useTaskProgress.ts
  frontend/src/hooks/useTaskCreate.ts
  frontend/src/components/layout/Navbar.tsx
  frontend/src/components/layout/Layout.tsx
  frontend/src/components/home/HeroSection.tsx
  frontend/src/components/home/ToolCard.tsx
  frontend/src/components/home/GallerySection.tsx
  frontend/src/components/home/GalleryCard.tsx
  frontend/src/components/workbench/ConfigPanel.tsx
  frontend/src/components/workbench/WorkflowConfig.tsx
  frontend/src/components/workbench/ImageUploader.tsx
  frontend/src/components/workbench/ResultPanel.tsx
  frontend/src/components/workbench/ImageGallery.tsx
  frontend/src/components/workbench/ResultCard.tsx
  frontend/src/components/common/ImageLightbox.tsx
  frontend/src/components/common/ProgressBar.tsx
  frontend/src/components/common/LoadingSpinner.tsx
  frontend/src/components/common/EmptyState.tsx
  frontend/src/pages/HomePage.tsx
  frontend/src/pages/WorkbenchPage.tsx
  frontend/src/pages/TaskDetailPage.tsx

Files to MODIFY:
  models.py                     # Add workflow_type, params to Task
  settings.py                   # Add image generation endpoints
  services/sophnet_client.py   # Add generate_image, edit_image methods
  services/llm_service.py      # Add product analysis, image prompt templates
  services/workflow.py         # Add product_set, remove_bg, model, edit workflows
  routers/tasks.py             # Add SSE endpoint, unified JSON task creation, upload
  routers/pages.py             # Serve SPA entry point, remove old templates
  app.py                       # CORS middleware, SPA static mount, remove Jinja2
```

---

## Phase 1: Foundation

### Task 1: Extend Task model with workflow_type and params

**Files:**
- Modify: `models.py`
- Modify: `database.py` (no change needed — init_db handles schema migration, but we need to handle existing rows)

**Interfaces:**
- Produces: `Task.workflow_type: str` (default "video"), `Task.params: str` (JSON, default "{}")
- Produces: `Task.image_model: str` (default "")

- [ ] **Step 1: Add new columns to Task model**

Open `models.py`. Replace the Task class with:

```python
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Text, primary_key=True, default=_uuid)
    status = Column(Text, nullable=False, default="pending")
    workflow_type = Column(Text, nullable=False, default="video")     # NEW
    image_paths = Column(Text, nullable=False, default="[]")
    specs = Column(Text, nullable=False, default="{}")
    params = Column(Text, nullable=False, default="{}")              # NEW: workflow-specific params
    llm_model = Column(Text, nullable=False, default="")
    video_model = Column(Text, nullable=False, default="")
    image_model = Column(Text, nullable=False, default="")           # NEW: image generation model
    result = Column(Text, nullable=False, default="{}")
    user_requirements = Column(Text, nullable=False, default="")
    error_message = Column(Text, nullable=True)
    created_at = Column(Text, nullable=False, default=_now)
    updated_at = Column(Text, nullable=False, default=_now)
```

- [ ] **Step 2: Delete and recreate database schema**

Since SQLite+aiosqlite doesn't support ALTER TABLE well, and this is a dev environment:

Run: `rm -f /media/cvitek/martin.xuan/dianshang/data.db`

The next time FastAPI starts, `init_db()` will create the schema with new columns.

- [ ] **Step 3: Verify startup**

Run: `cd /media/cvitek/martin.xuan/dianshang && timeout 5 python -c "import asyncio; from database import init_db; asyncio.run(init_db()); print('OK')"`

Expected: "OK" with no errors.

- [ ] **Step 4: Commit**

```bash
git add models.py
git commit -m "feat: extend Task model with workflow_type, params, image_model

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: Add image generation and edit methods to SophNetClient

**Files:**
- Modify: `services/sophnet_client.py`
- Modify: `settings.py`

**Interfaces:**
- Consumes: SophNet API endpoints
- Produces: `SophNetClient.generate_image(model, content, parameters?) -> dict`
- Produces: `SophNetClient.edit_image(model, content, parameters?) -> dict`
- Produces: `SophNetClient.query_image_task(task_id) -> dict`

- [ ] **Step 1: Add image generation endpoints to settings.py**

Open `settings.py`. Add after `video_query_url`:

```python
    # SophNet image generation endpoints
    image_gen_url: str = "https://www.sophnet.com/api/open-apis/projects/easyllms/imagegenerator/generate"
    image_query_url: str = "https://www.sophnet.com/api/open-apis/projects/easyllms/imagegenerator/task/{task_id}"
    image_edit_url: str = "https://www.sophnet.com/api/open-apis/projects/easyllms/imageeditor/edit"
    image_edit_query_url: str = "https://www.sophnet.com/api/open-apis/projects/easyllms/imageeditor/task/{task_id}"

    # Polling
    image_poll_interval_sec: int = 3
    image_timeout_sec: int = 300
```

- [ ] **Step 2: Add generate_image method to SophNetClient**

Open `services/sophnet_client.py`. Add after `generate_video` method:

```python
    async def generate_image(
        self, model: str, content: list[dict], parameters: dict | None = None
    ) -> dict:
        """Submit an image generation task to SophNet."""
        client = await self._get_client()
        body: dict = {"model": model, "content": content}
        if parameters:
            body["parameters"] = parameters

        resp = await client.post(SETTINGS.image_gen_url, json=body)
        resp.raise_for_status()
        return resp.json()

    async def edit_image(
        self, model: str, content: list[dict], parameters: dict | None = None
    ) -> dict:
        """Submit an image editing task to SophNet."""
        client = await self._get_client()
        body: dict = {"model": model, "content": content}
        if parameters:
            body["parameters"] = parameters

        resp = await client.post(SETTINGS.image_edit_url, json=body)
        resp.raise_for_status()
        return resp.json()

    async def query_image_task(self, task_id: str) -> dict:
        """Query the status of an image generation/editing task."""
        client = await self._get_client()
        url = SETTINGS.image_query_url.format(task_id=task_id)
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def query_edit_task(self, task_id: str) -> dict:
        """Query the status of an image editing task."""
        client = await self._get_client()
        url = SETTINGS.image_edit_query_url.format(task_id=task_id)
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 3: Verify syntax**

Run: `python -c "from services.sophnet_client import SophNetClient; print('OK')"`

Expected: "OK"

- [ ] **Step 4: Commit**

```bash
git add services/sophnet_client.py settings.py
git commit -m "feat: add image generation and edit methods to SophNetClient

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: Add image generation prompt templates to llm_service

**Files:**
- Modify: `services/llm_service.py`

**Interfaces:**
- Consumes: `SophNetClient.chat_completion()`
- Produces: `analyze_product_image(client, model, image_base64) -> dict` (renamed from analyze_image, enhanced output)
- Produces: `generate_image_prompts(client, model, analysis, params) -> dict`
- Produces: `parse_edit_instruction(client, model, instruction, image_description) -> dict`

- [ ] **Step 1: Rewrite analyze_image as analyze_product_image with richer output**

Open `services/llm_service.py`. Replace the `ANALYZE_IMAGE_PROMPT` and `analyze_image` function with:

```python
ANALYZE_PRODUCT_PROMPT = """你是一个电商产品分析专家。请仔细分析这张产品图片，输出详细的结构化分析。

你需要从以下维度进行分析，并严格输出 JSON（不要包含 markdown 标记或其他内容）：

{
  "category": "产品品类（中英文都写）",
  "material": "材质和表面处理细节",
  "style": "设计风格和视觉调性",
  "color_scheme": "详细配色方案（主色、辅色、点缀色）",
  "texture_detail": "材质纹理细节描述",
  "lighting": "当前图片的光线条件",
  "product_contour": "产品形状和轮廓描述",
  "key_features": ["卖点1", "卖点2", "卖点3", "卖点4", "卖点5"],
  "target_audience": "目标人群画像",
  "keep_intact": ["必须保留不变的元素1", "元素2", "元素3"],
  "suggested_scenes": ["适合的场景1", "场景2", "场景3"],
  "visual_highlights": "视觉亮点一段话描述"
}"""


async def analyze_product_image(client: SophNetClient, model: str, image_base64: str) -> dict:
    """Analyze product image using a vision-capable model. Returns rich structured analysis."""
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
            {"type": "text", "text": ANALYZE_PRODUCT_PROMPT},
        ],
    }]
    result = await client.chat_completion(model, messages, temperature=0.7)
    return _extract_json(result["content"])
```

- [ ] **Step 2: Add generate_image_prompts function**

Add after `analyze_product_image`:

```python
IMAGE_PROMPTS_TEMPLATE = """你是一个顶级的电商视觉设计师和AI图像生成提示词工程师。

根据以下产品分析结果和用户需求，为不同类型的电商图片生成精准的 AI 图像提示词。

产品分析：{analysis}
目标平台：{platform}
图片比例：{ratio}
输出语言：{language}
{requirements_block}

请严格输出 JSON（不要包含 markdown 标记）：

{{
  "white_bg": {{
    "cn_prompt": "纯白背景产品精修图的中文提示词（包含产品细节、构图、光线要求，确保产品主体完全保留原样）",
    "en_prompt": "English prompt for clean white background product image"
  }},
  "scenes": [
    {{
      "type": "场景类型标签",
      "cn_prompt": "该场景的中文提示词（包含场景、氛围、产品摆放、光线，确保产品主体完全保留原样）",
      "en_prompt": "English prompt for this scene"
    }}
  ],
  "selling_points": [
    {{
      "type": "卖点标签",
      "cn_prompt": "卖点展示图中文提示词（有文字标注空间，产品细节突出）",
      "en_prompt": "English prompt"
    }}
  ],
  "details": [
    {{
      "type": "细节类型",
      "cn_prompt": "细节特写中文提示词",
      "en_prompt": "English prompt"
    }}
  ],
  "size_chart": {{
    "cn_prompt": "尺寸/结构展示图中文提示词（如果产品适合做尺寸图；如果不适合则为空字符串）",
    "en_prompt": "English prompt"
  }}
}}

要求：
- 所有 prompt 必须以 "保持产品主体完全不变" 或 "Keep the product exactly as is" 开头
- 中文 prompt 要详细、具体、可用于图生图模型
- 场景图要多样化（不同使用场景、不同角度、不同氛围）
- 卖点图要预留标注空间
- 每个 prompt 中必须包含产品关键识别特征（从 product_contour 和 key_features 提取），确保生成图像中的产品与原图一致"""


async def generate_image_prompts(
    client: SophNetClient,
    model: str,
    analysis: dict,
    params: dict,
) -> dict:
    """Generate image generation prompts for all listing image types."""
    platform = params.get("platform", "通用电商平台")
    ratio = params.get("ratio", "1:1")
    language = params.get("language", "zh")
    requirements = params.get("requirements", "")
    req_block = f"\n用户补充要求：{requirements}" if requirements.strip() else ""

    prompt = IMAGE_PROMPTS_TEMPLATE.format(
        analysis=json.dumps(analysis, ensure_ascii=False),
        platform=platform,
        ratio=ratio,
        language=language,
        requirements_block=req_block,
    )
    messages = [{"role": "user", "content": prompt}]
    result = await client.chat_completion(model, messages, temperature=0.8)
    return _extract_json(result["content"])
```

- [ ] **Step 3: Add parse_edit_instruction function**

Add after `generate_image_prompts`:

```python
EDIT_PARSE_PROMPT = """你是一个 AI 图片编辑指令解析器。

用户原始指令：{instruction}
图片描述：{image_description}

请将用户的自然语言编辑请求解析为结构化的编辑参数，严格输出 JSON：

{{
  "action": "replace_background|replace_object|remove_object|add_object|adjust_style|other",
  "target": "要修改的目标区域/对象描述",
  "replacement": "替换为的新内容描述",
  "keep_intact": ["必须保持不变的元素"],
  "style_notes": "风格和氛围要求",
  "cn_prompt": "用于 AI 图片编辑的中文提示词（详细、具体）",
  "en_prompt": "English prompt for AI image editing"
}}"""


async def parse_edit_instruction(
    client: SophNetClient,
    model: str,
    instruction: str,
    image_description: str = "",
) -> dict:
    """Parse a natural language edit instruction into structured parameters."""
    prompt = EDIT_PARSE_PROMPT.format(instruction=instruction, image_description=image_description)
    messages = [{"role": "user", "content": prompt}]
    result = await client.chat_completion(model, messages, temperature=0.3)
    return _extract_json(result["content"])
```

- [ ] **Step 4: Update generate_promo_texts import (preserve backward compat)**

Add an alias at the bottom of the file to keep `analyze_image` working for the video workflow:

```python
# Backward compatibility alias for video workflow
analyze_image = analyze_product_image
```

- [ ] **Step 5: Verify syntax**

Run: `python -c "from services.llm_service import analyze_product_image, generate_image_prompts, parse_edit_instruction, analyze_image; print('OK')"`

Expected: "OK"

- [ ] **Step 6: Commit**

```bash
git add services/llm_service.py
git commit -m "feat: add product analysis, image prompt generation, and edit parsing to llm_service

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: Add image generation pipeline to video_service (reusable for all workflows)

**Files:**
- Create: `services/image_service.py`

**Interfaces:**
- Consumes: `SophNetClient.generate_image()`, `SophNetClient.query_image_task()`, `SophNetClient.download_file()`
- Produces: `submit_image_generation(client, model, image_paths, prompt_text, parameters?) -> dict`
- Produces: `poll_image_task(client, task_id) -> str`
- Produces: `generate_and_download_image(client, model, image_paths, prompt_text, task_id, output_subdir) -> str`
- Produces: `_extract_image_status(response) -> tuple[str, str|None]`

- [ ] **Step 1: Create image_service.py**

Create `services/image_service.py`:

```python
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
    """Submit an image generation task with reference images."""
    content = []
    for img_path in image_paths:
        content.append({
            "type": "image_url",
            "role": "reference_image",
            "image_url": {"url": _image_to_data_url(img_path)},
        })
    content.append({"type": "text", "text": prompt_text})

    return await client.generate_image(model, content, parameters)


async def submit_image_edit(
    client: SophNetClient,
    model: str,
    image_path: str,
    prompt_text: str,
    parameters: dict | None = None,
) -> dict:
    """Submit an image editing task."""
    content = [
        {"type": "image_url", "role": "input_image", "image_url": {"url": _image_to_data_url(image_path)}},
        {"type": "text", "text": prompt_text},
    ]
    return await client.edit_image(model, content, parameters)


def _extract_image_status(response: dict) -> tuple[str, str | None]:
    """Extract (status, image_url_or_error) from SophNet query response."""
    status = response.get("status", "")

    if status in ("succeeded", "completed", "success"):
        content = response.get("content", {})
        url = content.get("image_url") if isinstance(content, dict) else None
        if not url:
            # Try result array format
            results = response.get("result", [])
            if isinstance(results, list) and results:
                url = results[0].get("image_url") or results[0].get("url")
        return ("completed", url)

    if status in ("failed", "error"):
        error_obj = response.get("error", {})
        error_msg = error_obj.get("message", "Unknown error") if isinstance(error_obj, dict) else str(error_obj)
        return ("failed", error_msg)

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

    # Extract task_id from SophNet response
    inner = submit_result.get("result", {})
    sophnet_task_id = inner.get("task_id") if isinstance(inner, dict) else None
    if not sophnet_task_id:
        sophnet_task_id = submit_result.get("task_id") or submit_result.get("taskId")
    if not sophnet_task_id:
        raise SophNetError(f"Cannot extract task_id from response: {submit_result}")

    image_url = await poll_image_task(client, sophnet_task_id)

    task_dir = os.path.join(SETTINGS.output_dir, task_id, output_subdir)
    os.makedirs(task_dir, exist_ok=True)
    ext = ".png"
    local_path = os.path.join(task_dir, f"image_{image_index:02d}{ext}")
    await client.download_file(image_url, local_path)

    return local_path
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "from services.image_service import submit_image_generation, poll_image_task, generate_and_download_image; print('OK')"`

Expected: "OK"

- [ ] **Step 3: Commit**

```bash
git add services/image_service.py
git commit -m "feat: add image generation service (submit, poll, download)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: Implement new workflows

**Files:**
- Modify: `services/workflow.py`

**Interfaces:**
- Consumes: `analyze_product_image()`, `generate_image_prompts()`, `parse_edit_instruction()`
- Consumes: `generate_and_download_image()`, `generate_and_download()` (video)
- Consumes: `SophNetClient`
- Produces: `execute_workflow(task_id) -> None` (extended as dispatcher)
- Produces: `_run_product_set(client, task_id, db)`
- Produces: `_run_remove_bg(client, task_id, db)`
- Produces: `_run_model(client, task_id, db)`
- Produces: `_run_edit(client, task_id, db)`
- Produces: `_run_video(client, task_id, db)` (extracted from current execute_workflow)
- Produces: `_broadcast_progress(task_id, stage, **data)` for SSE

- [ ] **Step 1: Refactor execute_workflow as dispatcher, extract video workflow**

Open `services/workflow.py`. Replace the entire file content with the new implementation below.

First, we need a progress broadcast mechanism. Add this at the top after imports:

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
from services.image_service import generate_and_download_image, submit_image_edit, poll_image_task
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
```

- [ ] **Step 2: Write the execute_workflow dispatcher**

Add after the helper functions:

```python
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
```

- [ ] **Step 3: Write _run_product_set workflow**

```python
async def _run_product_set(client: SophNetClient, task_id: str):
    """Product set workflow: analyze -> prompts -> batch image generation."""
    async with async_session() as db:
        task = await db.get(Task, task_id)
        if not task:
            return
        image_paths = json.loads(task.image_paths)
        llm_model = task.llm_model
        image_model = task.image_model or "qwen-image-plus"
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
```

- [ ] **Step 4: Write _run_remove_bg workflow**

```python
async def _run_remove_bg(client: SophNetClient, task_id: str):
    """Remove background workflow: edit API to remove background."""
    async with async_session() as db:
        task = await db.get(Task, task_id)
        if not task:
            return
        image_paths = json.loads(task.image_paths)
        params = json.loads(task.params)
        image_model = task.image_model or "qwen-image-edit-2509"

    if not image_paths:
        raise ValueError("No input image provided")

    output_format = params.get("output_format", "both")  # "transparent", "white_bg", "both"
    result_images = []

    await _update_task_status(task_id, "processing", stage="removing_bg")
    await _broadcast_progress(task_id, "removing_bg", message="正在去除背景...")

    # Background removal prompt
    remove_bg_prompt = "Remove the background from this product image. Make the background completely transparent while keeping every detail of the product intact. The product edges should be sharp and clean. Output a transparent PNG."

    submit_result = await submit_image_edit(client, image_model, image_paths[0], remove_bg_prompt)

    inner = submit_result.get("result", {})
    st_id = inner.get("task_id") if isinstance(inner, dict) else None
    if not st_id:
        st_id = submit_result.get("task_id") or submit_result.get("taskId")
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
        inner2 = submit_result2.get("result", {})
        st_id2 = inner2.get("task_id") if isinstance(inner2, dict) else None
        if not st_id2:
            st_id2 = submit_result2.get("task_id") or submit_result2.get("taskId")
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
```

- [ ] **Step 5: Write _run_model workflow**

```python
async def _run_model(client: SophNetClient, task_id: str):
    """Model replacement workflow: analyze -> targeted edit -> multiple variants."""
    async with async_session() as db:
        task = await db.get(Task, task_id)
        if not task:
            return
        image_paths = json.loads(task.image_paths)
        llm_model = task.llm_model
        image_model = task.image_model or "qwen-image-edit-2509"
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
        inner = submit_result.get("result", {})
        st_id = inner.get("task_id") if isinstance(inner, dict) else None
        if not st_id:
            st_id = submit_result.get("task_id") or submit_result.get("taskId")
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
```

- [ ] **Step 6: Write _run_edit workflow**

```python
async def _run_edit(client: SophNetClient, task_id: str):
    """AI edit workflow: parse natural language -> edit image."""
    async with async_session() as db:
        task = await db.get(Task, task_id)
        if not task:
            return
        image_paths = json.loads(task.image_paths)
        llm_model = task.llm_model
        image_model = task.image_model or "qwen-image-edit-2509"
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

    inner = submit_result.get("result", {})
    st_id = inner.get("task_id") if isinstance(inner, dict) else None
    if not st_id:
        st_id = submit_result.get("task_id") or submit_result.get("taskId")
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
```

- [ ] **Step 7: Write _run_video workflow (extracted from current code, with progress broadcasts)**

```python
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
    async with async_session() as db:
        vt = VideoTask(
            task_id=task_id,
            shot_index="0",
            prompt=storyboard.get("en_prompt", storyboard.get("cn_prompt", "")),
            input_image=image_paths[0] if image_paths else "",
            status="pending",
        )
        db.add(vt)

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
    await _update_task_status(task_id, "completed", video=videos_result[0] if videos_result else None)
    await _broadcast_progress(task_id, "completed", video_path=rel_path)
```

- [ ] **Step 8: Verify syntax and imports**

Run: `python -c "from services.workflow import execute_workflow; print('OK')"`

Expected: "OK"

- [ ] **Step 9: Commit**

```bash
git add services/workflow.py
git commit -m "feat: implement product_set, remove_bg, model, edit workflows with SSE progress

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: Add API routes (upload, JSON task creation, SSE progress, gallery)

**Files:**
- Modify: `routers/tasks.py`

**Interfaces:**
- Consumes: `get_progress_queue()` from workflow
- Produces: `POST /api/upload → { file_paths }`
- Produces: `POST /api/tasks (JSON body) → { task_id, status }`
- Produces: `GET /api/tasks/:id/progress (SSE)`
- Produces: `GET /api/gallery → { tasks[] }`

- [ ] **Step 1: Add upload endpoint and JSON task creation to routers/tasks.py**

Open `routers/tasks.py`. Add at the top after existing imports:

```python
from services.workflow import execute_workflow, get_progress_queue
from fastapi.responses import StreamingResponse
```

Add upload endpoint before the existing `create_task`:

```python
@router.post("/upload")
async def upload_images(
    images: list[UploadFile] = File(...),
):
    """Upload images and return file paths. Used by React frontend before task creation."""
    if not images:
        raise HTTPException(status_code=400, detail="No images provided")
    if len(images) > 9:
        raise HTTPException(status_code=400, detail="最多支持 9 张图片")

    import uuid
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
```

- [ ] **Step 2: Add JSON-based task creation endpoint**

Add after the upload endpoint, before the existing `create_task`. Rename the old `create_task` to `create_task_form` to keep backward compat:

```python
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
    image_model = body.get("image_model", "qwen-image-plus")
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
```

**Note:** The original `create_task` with Form-based multipart stays for backward compatibility.

- [ ] **Step 3: Add SSE progress endpoint**

Add after the JSON creation endpoint:

```python
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
                current_result = json.loads(task.result)
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
```

- [ ] **Step 4: Add gallery endpoint**

```python
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
```

- [ ] **Step 5: Verify backend**

Run: `python -c "from routers.tasks import router; print('OK')"`

Expected: "OK"

- [ ] **Step 6: Commit**

```bash
git add routers/tasks.py
git commit -m "feat: add upload, JSON task creation, SSE progress, and gallery API endpoints

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: Update app.py for CORS and SPA serving

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: React SPA built files (will be in `frontend/dist/`)
- Produces: CORS middleware for dev, SPA catch-all route

- [ ] **Step 1: Add CORS and SPA catch-all**

Open `app.py`. Replace with:

```python
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers.config import router as config_router
from routers.pages import router as pages_router
from routers.tasks import router as tasks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="电商AI内容生产工具", lifespan=lifespan)

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# Routers
app.include_router(pages_router)
app.include_router(tasks_router)
app.include_router(config_router)

# Serve React SPA from frontend/dist
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="spa_assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str = ""):
        """Serve React SPA — catch-all that returns index.html for client-side routing."""
        # API routes are already handled by routers, this only catches non-API paths
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return FileResponse(index_path, status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
```

- [ ] **Step 2: Verify app starts**

Run: `cd /media/cvitek/martin.xuan/dianshang && timeout 5 python app.py 2>&1 || true`

Expected: Uvicorn starts without import errors.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add CORS, SPA catch-all routing, remove Jinja2 dependency

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Phase 2: React Frontend

### Task 8: Scaffold React + Vite + Tailwind project

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`
- Create: `frontend/tailwind.config.ts`, `frontend/index.html`, `frontend/src/main.tsx`
- Create: `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/lib/utils.ts`

- [ ] **Step 1: Initialize project**

Run:
```bash
cd /media/cvitek/martin.xuan/dianshang
npm create vite@latest frontend -- --template react-ts 2>&1
cd frontend
npm install 2>&1
npm install react-router-dom framer-motion lucide-react 2>&1
npm install -D tailwindcss @tailwindcss/vite 2>&1
```

- [ ] **Step 2: Configure Vite with API proxy and Tailwind**

Write `frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8080',
      '/uploads': 'http://localhost:8080',
      '/outputs': 'http://localhost:8080',
    },
  },
})
```

- [ ] **Step 3: Configure Tailwind with dark theme tokens**

Write `frontend/src/index.css`:

```css
@import "tailwindcss";

@theme {
  --color-bg-primary: #0a0a0f;
  --color-bg-card: #13131a;
  --color-bg-card-hover: #1a1a24;
  --color-accent: #6366f1;
  --color-accent-glow: rgba(99, 102, 241, 0.15);
  --color-text-primary: #e4e4e7;
  --color-text-secondary: #71717a;
  --color-border-subtle: rgba(255, 255, 255, 0.06);
  --color-border-card: rgba(255, 255, 255, 0.08);
  --color-border-glow: rgba(99, 102, 241, 0.3);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #root {
  height: 100%;
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
```

- [ ] **Step 4: Write App.tsx with router**

Write `frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import { HomePage } from './pages/HomePage'
import { WorkbenchPage } from './pages/WorkbenchPage'
import { TaskDetailPage } from './pages/TaskDetailPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/tools/:type" element={<WorkbenchPage />} />
          <Route path="/task/:id" element={<TaskDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 5: Write main.tsx**

Write `frontend/src/main.tsx`:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 6: Write index.html**

Write `frontend/index.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>电商AI内容生产工具</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 7: Write cn() utility**

Write `frontend/src/lib/utils.ts`:

```typescript
export function cn(...classes: (string | undefined | false)[]): string {
  return classes.filter(Boolean).join(' ')
}
```

- [ ] **Step 8: Write TypeScript types**

Write `frontend/src/types/index.ts`:

```typescript
export type WorkflowType = 'product_set' | 'remove_bg' | 'model' | 'video' | 'edit'

export interface TaskParams {
  workflow_type: WorkflowType
  image_paths: string[]
  params: Record<string, unknown>
  user_requirements?: string
  llm_model?: string
  video_model?: string
  image_model?: string
  specs?: Record<string, string>
}

export interface ProgressEvent {
  stage: string
  current?: number
  total?: number
  message?: string
  image_type?: string
  preview_url?: string
  result_images?: ResultImage[]
  video_path?: string
  error?: string
}

export interface ResultImage {
  type: string
  path: string
  index?: number
}

export interface ToolInfo {
  id: WorkflowType
  title: string
  description: string
  icon: string
  gradient: string
}
```

- [ ] **Step 9: Verify dev server starts**

Run:
```bash
cd /media/cvitek/martin.xuan/dianshang/frontend && timeout 10 npm run dev 2>&1 || true
```

Expected: Vite dev server starts on port 3000.

- [ ] **Step 10: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold React + Vite + Tailwind project with dark theme

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 9: Build Layout, Navbar, and API client

**Files:**
- Create: `frontend/src/components/layout/Navbar.tsx`
- Create: `frontend/src/components/layout/Layout.tsx`
- Create: `frontend/src/api/client.ts`

- [ ] **Step 1: Write API client**

Write `frontend/src/api/client.ts`:

```typescript
const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  upload: async (files: FileList): Promise<{ file_paths: string[]; batch_id: string }> => {
    const form = new FormData()
    Array.from(files).forEach(f => form.append('images', f))
    const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  createTask: (data: Record<string, unknown>) =>
    request<{ task_id: string; status: string }>(`/tasks/json`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getTask: (id: string) => request<any>(`/tasks/${id}`),

  getGallery: () => request<{ tasks: any[] }>('/tasks/gallery/list'),

  progressUrl: (id: string) => `${BASE}/tasks/${id}/progress`,
}
```

- [ ] **Step 2: Write Navbar**

Write `frontend/src/components/layout/Navbar.tsx`:

```tsx
import { Link, useNavigate } from 'react-router-dom'
import { Image, Video, Wand2 } from 'lucide-react'

const navItems = [
  { to: '/', label: 'AI 图片', icon: Image },
  { to: '/tools/video', label: 'AI 视频', icon: Video },
  { to: '/tools/edit', label: 'AI 编辑', icon: Wand2 },
]

export function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-16 border-b border-border-subtle bg-bg-primary/80 backdrop-blur-xl">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2">
          <span className="text-xl font-bold text-text-primary">电商AI</span>
        </Link>

        <div className="flex items-center gap-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-text-secondary
                         hover:text-text-primary hover:bg-bg-card transition-colors"
            >
              <Icon size={16} />
              {label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/settings"
            className="text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            设置
          </Link>
        </div>
      </div>
    </nav>
  )
}
```

- [ ] **Step 3: Write Layout**

Write `frontend/src/components/layout/Layout.tsx`:

```tsx
import { Outlet } from 'react-router-dom'
import { Navbar } from './Navbar'

export function Layout() {
  return (
    <div className="min-h-screen bg-bg-primary">
      <Navbar />
      <main className="pt-16">
        <Outlet />
      </main>
    </div>
  )
}
```

- [ ] **Step 4: Verify build**

Run: `cd /media/cvitek/martin.xuan/dianshang/frontend && npx tsc --noEmit 2>&1 | head -20`

Fix any type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: add Layout, Navbar, and API client

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 10: Build HomePage with ToolCard grid and Hero

**Files:**
- Create: `frontend/src/pages/HomePage.tsx`
- Create: `frontend/src/components/home/HeroSection.tsx`
- Create: `frontend/src/components/home/ToolCard.tsx`

- [ ] **Step 1: Write TOOLS data**

Add after the `ToolInfo` type in `frontend/src/types/index.ts`:

```typescript
export const TOOLS: ToolInfo[] = [
  {
    id: 'product_set',
    title: '商品套图',
    description: '上传商品图，一键生成白底图、场景图、卖点图等全套电商素材',
    icon: '🛍️',
    gradient: 'from-indigo-500/20 to-purple-600/20',
  },
  {
    id: 'remove_bg',
    title: 'AI 抠图',
    description: '精准去除背景，生成透明 PNG 和白底商品图',
    icon: '✂️',
    gradient: 'from-emerald-500/20 to-teal-600/20',
  },
  {
    id: 'model',
    title: 'AI 模特',
    description: '智能替换模特、背景，生成多场景展示图',
    icon: '👤',
    gradient: 'from-orange-500/20 to-pink-600/20',
  },
  {
    id: 'video',
    title: 'AI 视频',
    description: '从商品图生成 15 秒带货短视频，带文案和配音',
    icon: '▶️',
    gradient: 'from-blue-500/20 to-cyan-600/20',
  },
  {
    id: 'edit',
    title: 'AI 编辑',
    description: '用自然语言编辑图片，替换背景、修改元素、调整风格',
    icon: '🖌️',
    gradient: 'from-rose-500/20 to-red-600/20',
  },
]
```

- [ ] **Step 2: Write HeroSection**

Write `frontend/src/components/home/HeroSection.tsx`:

```tsx
export function HeroSection() {
  return (
    <section className="py-20 text-center">
      <h1 className="text-4xl font-bold text-text-primary sm:text-5xl">
        你的 AI 电商创意工作台
      </h1>
      <p className="mt-4 text-lg text-text-secondary">
        从商品图到全套素材，AI 自动完成专业制作
      </p>
    </section>
  )
}
```

- [ ] **Step 3: Write ToolCard**

Write `frontend/src/components/home/ToolCard.tsx`:

```tsx
import { useNavigate } from 'react-router-dom'
import type { ToolInfo } from '../../types'

export function ToolCard({ tool }: { tool: ToolInfo }) {
  const navigate = useNavigate()

  return (
    <button
      onClick={() => navigate(`/tools/${tool.id}`)}
      className={`group relative flex flex-col items-start gap-3 rounded-2xl border border-border-card
                  bg-gradient-to-br ${tool.gradient} p-6 text-left
                  transition-all duration-300 hover:scale-[1.02] hover:border-border-glow
                  hover:shadow-[0_0_30px_rgba(99,102,241,0.1)]`}
    >
      <span className="text-3xl">{tool.icon}</span>
      <h3 className="text-lg font-semibold text-text-primary">{tool.title}</h3>
      <p className="text-sm text-text-secondary">{tool.description}</p>
    </button>
  )
}
```

- [ ] **Step 4: Write HomePage**

Write `frontend/src/pages/HomePage.tsx`:

```tsx
import { HeroSection } from '../components/home/HeroSection'
import { ToolCard } from '../components/home/ToolCard'
import { TOOLS } from '../types'

export function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <HeroSection />

      <section className="mt-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TOOLS.slice(0, 3).map(tool => (
            <ToolCard key={tool.id} tool={tool} />
          ))}
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {TOOLS.slice(3, 5).map(tool => (
            <ToolCard key={tool.id} tool={tool} />
          ))}
        </div>
      </section>
    </div>
  )
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: add HomePage with Hero section and ToolCard grid

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 11: Build WorkbenchPage with ConfigPanel and ResultPanel

**Files:**
- Create: `frontend/src/pages/WorkbenchPage.tsx`
- Create: `frontend/src/components/workbench/ImageUploader.tsx`
- Create: `frontend/src/components/workbench/WorkflowConfig.tsx`
- Create: `frontend/src/components/workbench/ResultPanel.tsx`
- Create: `frontend/src/components/workbench/ImageGallery.tsx`
- Create: `frontend/src/components/workbench/ResultCard.tsx`
- Create: `frontend/src/hooks/useTaskProgress.ts`
- Create: `frontend/src/hooks/useTaskCreate.ts`

- [ ] **Step 1: Write useTaskCreate hook**

Write `frontend/src/hooks/useTaskCreate.ts`:

```typescript
import { useState } from 'react'
import { api } from '../api/client'

export function useTaskCreate() {
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function create(data: Record<string, unknown>) {
    setCreating(true)
    setError(null)
    try {
      const result = await api.createTask(data)
      return result.task_id
    } catch (e: any) {
      setError(e.message)
      return null
    } finally {
      setCreating(false)
    }
  }

  return { create, creating, error }
}
```

- [ ] **Step 2: Write useTaskProgress hook**

Write `frontend/src/hooks/useTaskProgress.ts`:

```typescript
import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'
import type { ProgressEvent, ResultImage } from '../types'

export function useTaskProgress(taskId: string | null) {
  const [stage, setStage] = useState('')
  const [message, setMessage] = useState('')
  const [current, setCurrent] = useState(0)
  const [total, setTotal] = useState(0)
  const [results, setResults] = useState<ResultImage[]>([])
  const [previewUrls, setPreviewUrls] = useState<string[]>([])
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!taskId) return

    const es = new EventSource(api.progressUrl(taskId))

    es.onmessage = (e) => {
      const data: ProgressEvent = JSON.parse(e.data)
      setStage(data.stage)
      if (data.message) setMessage(data.message)
      if (data.current !== undefined) setCurrent(data.current)
      if (data.total !== undefined) setTotal(data.total)

      if (data.preview_url) {
        setPreviewUrls(prev => [...prev, data.preview_url])
      }

      if (data.result_images) {
        setResults(data.result_images)
      }

      if (data.stage === 'completed') {
        setDone(true)
        es.close()
      }
      if (data.stage === 'failed') {
        setError(data.error || 'Task failed')
        es.close()
      }
    }

    es.onerror = () => {
      // EventSource auto-reconnects; only close if task is done
      if (done) es.close()
    }

    return () => es.close()
  }, [taskId])

  return { stage, message, current, total, results, previewUrls, done, error }
}
```

- [ ] **Step 3: Write ImageUploader**

Write `frontend/src/components/workbench/ImageUploader.tsx`:

```tsx
import { useCallback, useState } from 'react'
import { Upload, X } from 'lucide-react'

interface Props {
  files: File[]
  onFilesChange: (files: File[]) => void
}

export function ImageUploader({ files, onFilesChange }: Props) {
  const [dragging, setDragging] = useState(false)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const dropped = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'))
    onFilesChange([...files, ...dropped].slice(0, 9))
  }, [files, onFilesChange])

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files)
      onFilesChange([...files, ...selected].slice(0, 9))
    }
  }

  const removeFile = (idx: number) => {
    onFilesChange(files.filter((_, i) => i !== idx))
  }

  return (
    <div className="space-y-3">
      <label className="text-sm font-medium text-text-secondary">上传商品图片</label>

      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8
                    transition-colors cursor-pointer
                    ${dragging
                      ? 'border-accent bg-accent-glow'
                      : 'border-border-card hover:border-border-glow'}`}
        onClick={() => document.getElementById('file-input')?.click()}
      >
        <Upload size={24} className="text-text-secondary" />
        <p className="text-sm text-text-secondary">拖拽图片到此处或点击上传</p>
        <p className="text-xs text-text-secondary/60">最多 9 张，单张不超过 20MB</p>
        <input
          id="file-input"
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={handleFileInput}
        />
      </div>

      {files.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {files.map((f, i) => (
            <div key={i} className="group relative">
              <img
                src={URL.createObjectURL(f)}
                alt={f.name}
                className="h-16 w-16 rounded-lg object-cover"
              />
              <button
                onClick={(e) => { e.stopPropagation(); removeFile(i) }}
                className="absolute -right-1.5 -top-1.5 rounded-full bg-bg-card p-0.5
                           opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X size={14} className="text-text-secondary" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Write WorkflowConfig**

Write `frontend/src/components/workbench/WorkflowConfig.tsx`:

```tsx
import type { WorkflowType } from '../../types'

interface Props {
  type: WorkflowType
  params: Record<string, string>
  onParamChange: (key: string, value: string) => void
}

export function WorkflowConfig({ type, params, onParamChange }: Props) {
  const inputClass = "w-full rounded-lg border border-border-card bg-bg-card px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none transition-colors"
  const labelClass = "text-sm font-medium text-text-secondary"

  if (type === 'product_set') {
    return (
      <div className="space-y-4">
        <div>
          <label className={labelClass}>目标平台</label>
          <select className={inputClass} value={params.platform || ''}
                  onChange={e => onParamChange('platform', e.target.value)}>
            <option value="">通用电商平台</option>
            <option value="亚马逊">亚马逊</option>
            <option value="Temu">Temu</option>
            <option value="速卖通">速卖通</option>
            <option value="独立站">独立站</option>
          </select>
        </div>

        <div>
          <label className={labelClass}>图片比例</label>
          <select className={inputClass} value={params.ratio || ''}
                  onChange={e => onParamChange('ratio', e.target.value)}>
            <option value="1:1">1:1 (正方形)</option>
            <option value="4:5">4:5 (竖版)</option>
            <option value="16:9">16:9 (横版)</option>
            <option value="3:4">3:4</option>
          </select>
        </div>

        <div>
          <label className={labelClass}>语言</label>
          <select className={inputClass} value={params.language || ''}
                  onChange={e => onParamChange('language', e.target.value)}>
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </div>

        <div>
          <label className={labelClass}>补充要求（选填）</label>
          <textarea className={inputClass} rows={3} value={params.requirements || ''}
                    onChange={e => onParamChange('requirements', e.target.value)}
                    placeholder="例如：清新高级风格，适合美妆品类..." />
        </div>
      </div>
    )
  }

  if (type === 'remove_bg') {
    return (
      <div>
        <label className={labelClass}>输出格式</label>
        <select className={inputClass} value={params.output_format || 'both'}
                onChange={e => onParamChange('output_format', e.target.value)}>
          <option value="both">透明 PNG + 白底图</option>
          <option value="transparent">仅透明 PNG</option>
          <option value="white_bg">仅白底图</option>
        </select>
      </div>
    )
  }

  if (type === 'model') {
    return (
      <div className="space-y-4">
        <div>
          <label className={labelClass}>替换描述</label>
          <textarea className={inputClass} rows={3} value={params.replacement_desc || ''}
                    onChange={e => onParamChange('replacement_desc', e.target.value)}
                    placeholder="例如：将背景替换为海边沙滩场景，模特换为欧美风格..." />
        </div>
        <div>
          <label className={labelClass}>生成数量</label>
          <select className={inputClass} value={params.num_variants || '3'}
                  onChange={e => onParamChange('num_variants', e.target.value)}>
            <option value="1">1 张</option>
            <option value="2">2 张</option>
            <option value="3">3 张</option>
            <option value="4">4 张</option>
          </select>
        </div>
      </div>
    )
  }

  if (type === 'video') {
    return (
      <div className="space-y-4">
        <div>
          <label className={labelClass}>LLM 模型</label>
          <select className={inputClass} value={params.llm_model || 'DeepSeek-V4-Flash-Vision-Exp'}
                  onChange={e => onParamChange('llm_model', e.target.value)}>
            <option value="DeepSeek-V4-Flash-Vision-Exp">DeepSeek-V4-Flash-Vision-Exp</option>
            <option value="glm-4-flash">GLM-4-Flash</option>
          </select>
        </div>
        <div>
          <label className={labelClass}>视频模型</label>
          <select className={inputClass} value={params.video_model || 'happyhorse-1.1-i2v'}
                  onChange={e => onParamChange('video_model', e.target.value)}>
            <option value="happyhorse-1.1-i2v">HappyHorse-1.1-i2v</option>
            <option value="happyhorse-1.0-r2v">HappyHorse-1.0-r2v</option>
            <option value="wan2.7">WAN 2.7</option>
          </select>
        </div>
        <div>
          <label className={labelClass}>补充要求（选填）</label>
          <textarea className={inputClass} rows={3} value={params.requirements || ''}
                    onChange={e => onParamChange('requirements', e.target.value)}
                    placeholder="例如：希望视频呈现出温馨日系的风格..." />
        </div>
      </div>
    )
  }

  // edit type
  return (
    <div>
      <label className={labelClass}>编辑指令</label>
      <textarea className={inputClass} rows={3} value={params.edit_instruction || ''}
                onChange={e => onParamChange('edit_instruction', e.target.value)}
                placeholder="例如：把背景换成白色，去掉水印，调亮画面..." />
    </div>
  )
}
```

- [ ] **Step 5: Write ResultCard and ImageGallery**

Write `frontend/src/components/workbench/ResultCard.tsx`:

```tsx
import { Download } from 'lucide-react'
import type { ResultImage } from '../../types'

interface Props {
  image: ResultImage
  onPreview: (path: string) => void
}

const typeLabels: Record<string, string> = {
  white_bg: '白底图',
  scene: '场景图',
  selling_point: '卖点图',
  detail: '详情图',
  size_chart: '尺寸图',
  transparent: '透明PNG',
  white_bg_out: '白底图',
  variant: '变体',
  edited: '编辑结果',
}

export function ResultCard({ image, onPreview }: Props) {
  const fullUrl = image.path

  return (
    <div className="group relative overflow-hidden rounded-xl border border-border-card bg-bg-card
                    transition-all duration-300 hover:border-border-glow hover:shadow-lg">
      <img
        src={fullUrl}
        alt={image.type}
        className="h-48 w-full object-cover cursor-pointer"
        onClick={() => onPreview(fullUrl)}
        loading="lazy"
      />
      <div className="flex items-center justify-between px-3 py-2">
        <span className="text-xs text-text-secondary">{typeLabels[image.type] || image.type}</span>
        <a
          href={fullUrl}
          download
          className="rounded p-1 text-text-secondary hover:text-text-primary transition-colors"
          onClick={e => e.stopPropagation()}
        >
          <Download size={14} />
        </a>
      </div>
    </div>
  )
}
```

Write `frontend/src/components/workbench/ImageGallery.tsx`:

```tsx
import { useState } from 'react'
import type { ResultImage } from '../../types'
import { ResultCard } from './ResultCard'

interface Props {
  images: ResultImage[]
  previewUrls?: string[]
}

export function ImageGallery({ images, previewUrls = [] }: Props) {
  const [preview, setPreview] = useState<string | null>(null)

  // Show preview URLs while waiting for final results
  const displayImages = images.length > 0
    ? images
    : previewUrls.map(url => ({ type: 'preview', path: url }))

  if (displayImages.length === 0) return null

  return (
    <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {displayImages.map((img, i) => (
          <ResultCard key={i} image={img} onPreview={setPreview} />
        ))}
      </div>

      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setPreview(null)}
        >
          <img
            src={preview}
            alt="Preview"
            className="max-h-[90vh] max-w-[90vw] rounded-xl object-contain"
          />
        </div>
      )}
    </>
  )
}
```

- [ ] **Step 6: Write ResultPanel**

Write `frontend/src/components/workbench/ResultPanel.tsx`:

```tsx
import { Download, RefreshCw } from 'lucide-react'
import type { ResultImage } from '../../types'
import { ImageGallery } from './ImageGallery'

interface Props {
  results: ResultImage[]
  previewUrls: string[]
  stage: string
  message: string
  current: number
  total: number
  done: boolean
  error: string | null
  onRetry: () => void
}

export function ResultPanel({ results, previewUrls, stage, message, current, total, done, error, onRetry }: Props) {
  const hasContent = results.length > 0 || previewUrls.length > 0

  return (
    <div className="space-y-4">
      {/* Progress */}
      {!done && stage && stage !== 'connected' && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-text-secondary">{message}</span>
            {total > 0 && (
              <span className="text-accent">{current}/{total}</span>
            )}
          </div>
          {total > 0 && (
            <div className="h-1 w-full overflow-hidden rounded-full bg-bg-card">
              <div
                className="h-full rounded-full bg-accent transition-all duration-500"
                style={{ width: `${(current / total) * 100}%` }}
              />
            </div>
          )}
          {total === 0 && (
            <div className="h-1 w-full overflow-hidden rounded-full bg-bg-card">
              <div className="h-full w-1/3 animate-pulse rounded-full bg-accent" />
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <p className="text-sm text-red-400">{error}</p>
          <button onClick={onRetry}
                  className="mt-2 inline-flex items-center gap-1.5 text-sm text-red-400 hover:text-red-300">
            <RefreshCw size={14} /> 重试
          </button>
        </div>
      )}

      {/* Results */}
      {hasContent && (
        <ImageGallery images={results} previewUrls={previewUrls} />
      )}

      {/* Empty state */}
      {!hasContent && !stage && (
        <div className="flex flex-col items-center justify-center py-16 text-text-secondary">
          <p className="text-sm">上传图片并配置参数后开始生成</p>
        </div>
      )}

      {/* Download all */}
      {done && results.length > 0 && (
        <div className="flex justify-end">
          <button
            onClick={() => results.forEach(r => {
              const a = document.createElement('a')
              a.href = r.path
              a.download = ''
              a.click()
            })}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm text-white
                       hover:bg-accent/90 transition-colors"
          >
            <Download size={16} /> 下载全部
          </button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 7: Write WorkbenchPage**

Write `frontend/src/pages/WorkbenchPage.tsx`:

```tsx
import { useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { ImageUploader } from '../components/workbench/ImageUploader'
import { WorkflowConfig } from '../components/workbench/WorkflowConfig'
import { ResultPanel } from '../components/workbench/ResultPanel'
import { useTaskCreate } from '../hooks/useTaskCreate'
import { useTaskProgress } from '../hooks/useTaskProgress'
import { api } from '../api/client'
import { TOOLS, type WorkflowType } from '../types'

const toolTitles: Record<string, string> = {
  product_set: '商品套图',
  remove_bg: 'AI 抠图',
  model: 'AI 模特',
  video: 'AI 视频',
  edit: 'AI 编辑',
}

export function WorkbenchPage() {
  const { type } = useParams<{ type: string }>()
  const workflowType = (type || 'product_set') as WorkflowType
  const toolInfo = TOOLS.find(t => t.id === workflowType)

  const [files, setFiles] = useState<File[]>([])
  const [params, setParams] = useState<Record<string, string>>({})
  const [taskId, setTaskId] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  const { create, creating } = useTaskCreate()
  const { stage, message, current, total, results, previewUrls, done, error } = useTaskProgress(taskId)

  const handleParamChange = useCallback((key: string, value: string) => {
    setParams(prev => ({ ...prev, [key]: value }))
  }, [])

  const handleGenerate = async () => {
    if (files.length === 0) {
      alert('请先上传图片')
      return
    }

    // Upload images first
    const uploadResult = await api.upload(files as unknown as FileList)
    if (!uploadResult.file_paths?.length) {
      alert('上传失败')
      return
    }

    const taskData: Record<string, unknown> = {
      workflow_type: workflowType,
      image_paths: uploadResult.file_paths,
      params,
    }

    if (workflowType === 'video') {
      taskData.llm_model = params.llm_model || 'DeepSeek-V4-Flash-Vision-Exp'
      taskData.video_model = params.video_model || 'happyhorse-1.1-i2v'
      taskData.user_requirements = params.requirements || ''
      taskData.specs = {}
    } else {
      taskData.user_requirements = params.requirements || params.edit_instruction || params.replacement_desc || ''
      taskData.image_model = 'qwen-image-plus'
    }

    const id = await create(taskData)
    if (id) setTaskId(id)
  }

  const handleRetry = () => {
    setTaskId(null)
    setRetryKey(k => k + 1)
    handleGenerate()
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <Link to="/" className="rounded-lg p-1.5 text-text-secondary hover:text-text-primary transition-colors">
          <ArrowLeft size={20} />
        </Link>
        <h1 className="text-xl font-semibold text-text-primary">
          {toolTitles[workflowType] || workflowType}
        </h1>
      </div>

      {/* Split layout */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Left: Config */}
        <div className="space-y-6" key={retryKey}>
          <ImageUploader files={files} onFilesChange={setFiles} />

          {workflowType !== 'video' && (
            <WorkflowConfig type={workflowType} params={params} onParamChange={handleParamChange} />
          )}
          {workflowType === 'video' && (
            <WorkflowConfig type="video" params={params} onParamChange={handleParamChange} />
          )}

          <button
            onClick={handleGenerate}
            disabled={creating || files.length === 0}
            className="w-full rounded-xl bg-accent py-3 text-sm font-semibold text-white
                       hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-300 hover:shadow-[0_0_20px_rgba(99,102,241,0.3)]"
          >
            {creating ? '⏳ 正在创建任务...' : '🚀 开始生成'}
          </button>
        </div>

        {/* Right: Results */}
        <div>
          <ResultPanel
            results={results}
            previewUrls={previewUrls}
            stage={stage}
            message={message}
            current={current}
            total={total}
            done={done}
            error={error}
            onRetry={handleRetry}
          />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 8: Verify TypeScript**

Run: `cd /media/cvitek/martin.xuan/dianshang/frontend && npx tsc --noEmit 2>&1 | head -30`

Fix any type errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/
git commit -m "feat: add WorkbenchPage with upload, config, SSE progress, and result gallery

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 12: Build TaskDetailPage

**Files:**
- Create: `frontend/src/pages/TaskDetailPage.tsx`

- [ ] **Step 1: Write TaskDetailPage**

Write `frontend/src/pages/TaskDetailPage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { api } from '../api/client'
import { ImageGallery } from '../components/workbench/ImageGallery'

export function TaskDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [task, setTask] = useState<any>(null)

  useEffect(() => {
    if (id) {
      api.getTask(id).then(setTask).catch(console.error)
    }
  }, [id])

  if (!task) {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  const resultImages = task.result?.result_images || []

  const statusBadge: Record<string, string> = {
    pending: 'bg-yellow-500/20 text-yellow-400',
    processing: 'bg-blue-500/20 text-blue-400',
    completed: 'bg-green-500/20 text-green-400',
    failed: 'bg-red-500/20 text-red-400',
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6 flex items-center gap-3">
        <Link to="/" className="rounded-lg p-1.5 text-text-secondary hover:text-text-primary transition-colors">
          <ArrowLeft size={20} />
        </Link>
        <h1 className="text-xl font-semibold text-text-primary">任务详情</h1>
        <span className={`rounded-full px-2.5 py-0.5 text-xs ${statusBadge[task.status] || ''}`}>
          {task.status}
        </span>
      </div>

      {task.status === 'completed' && resultImages.length > 0 && (
        <ImageGallery images={resultImages} />
      )}

      {task.status === 'completed' && task.result?.video && (
        <div className="mt-6">
          {task.result.video.path && (
            <video controls className="w-full rounded-xl" src={task.result.video.path} />
          )}
        </div>
      )}

      {task.status === 'failed' && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6">
          <p className="text-red-400">{task.error_message}</p>
        </div>
      )}

      {task.status === 'processing' && (
        <div className="flex flex-col items-center gap-4 py-16">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          <p className="text-text-secondary">任务正在处理中...</p>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/TaskDetailPage.tsx
git commit -m "feat: add TaskDetailPage with result display

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Phase 3: Build, Integration & Deploy

### Task 13: Build React SPA and verify FastAPI serves it

- [ ] **Step 1: Build frontend**

```bash
cd /media/cvitek/martin.xuan/dianshang/frontend && npm run build
```

Expected: `dist/` directory created with `index.html` and `assets/`.

- [ ] **Step 2: Start FastAPI and verify SPA loads**

```bash
cd /media/cvitek/martin.xuan/dianshang && python app.py &
sleep 3
curl -s http://localhost:8080/ | head -20
kill %1
```

Expected: The response should contain the React `index.html` content (not Jinja2 template).

- [ ] **Step 3: Verify API still works**

```bash
cd /media/cvitek/martin.xuan/dianshang && python app.py &
sleep 3
curl -s http://localhost:8080/api/tasks | head -5
kill %1
```

Expected: JSON response with tasks list.

- [ ] **Step 4: Commit**

```bash
git add frontend/dist
git commit -m "feat: build React SPA and verify FastAPI integration

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 14: End-to-end smoke test

- [ ] **Step 1: Test backend startup**

```bash
cd /media/cvitek/martin.xuan/dianshang && python -c "
import asyncio
from database import init_db, async_session
from models import Task

async def test():
    await init_db()
    async with async_session() as db:
        from sqlalchemy import select
        result = await db.execute(select(Task).limit(1))
        print('DB OK:', result.scalars().all())
asyncio.run(test())
"
```

- [ ] **Step 2: Test upload API**

```bash
# Create a small test image
python -c "
from PIL import Image
img = Image.new('RGB', (100, 100), color='blue')
img.save('/tmp/test_product.jpg')
"

# Start server in background
cd /media/cvitek/martin.xuan/dianshang && python app.py &
sleep 3

# Test upload
curl -s -F "images=@/tmp/test_product.jpg" http://localhost:8080/api/upload

kill %1
```

- [ ] **Step 3: Integrate remaining old-style pages (settings page)**

Add to `app.py` after the SPA catch-all to avoid conflicts with settings page:

```python
    # Settings page served by FastAPI (not SPA)
    @app.get("/settings")
    async def serve_settings():
        """Keep old settings page until migrated to React."""
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return FileResponse(index_path, status_code=404)
```

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "chore: add settings route for SPA, end-to-end verification

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Plan Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| Phase 1 | 1-7 | Backend: model extension, SophNet image API, LLM prompt templates, image service, 5 workflows, API routes (upload/SSE/gallery), app.py CORS+SPA |
| Phase 2 | 8-12 | Frontend: Vite+React+Tailwind scaffold, Layout+Navbar, API client, HomePage with ToolCards, WorkbenchPage (upload+config+progress+gallery), TaskDetailPage |
| Phase 3 | 13-14 | Build, integration verification, deploy |

Total: 14 tasks across 3 phases. Each task produces independently testable output.