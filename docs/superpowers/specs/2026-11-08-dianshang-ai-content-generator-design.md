# 淘宝电商铺货 AI 内容生产工具 — 系统设计文档

> 版本: v1.0 | 日期: 2026-11-08 | 状态: 待评审

---

## 1. 项目概要

### 1.1 目标

构建一个个人使用的 Web 工具，输入产品图片和规格信息，通过 SophNet 算力平台统一调用大模型（DeepSeek/GLM/Kimi）自动生成：产品图片分析 → 宣传文案与营销提示词 → AI 视频分镜头脚本 → 调用 WAN2.7 / HappyHorse 生成宣传视频。

### 1.2 核心约束

| 项目 | 选择 |
|------|------|
| 目标用户 | 单用户，个人工具 |
| 技术栈 | Python FastAPI + Jinja2 + HTMX + SQLite |
| API 平台 | SophNet（统一 OpenAI 兼容接口） |
| 文本模型 | DeepSeek-V4-Flash-Vision-Exp, glm-4-flash, kimi 等 |
| 视频模型 | WAN2.7 (文生视频/图生视频), HappyHorse-1.1-i2v (图生视频) |
| 部署方式 | 本机 `python app.py`，无需容器化 |

---

## 2. 系统架构

### 2.1 架构图

```
┌──────────────────────────────────────────────────────┐
│                     FastAPI 服务                       │
│                                                      │
│  ┌──────────┐   ┌─────────────┐   ┌─────────────┐   │
│  │  Web UI  │   │  REST APIs  │   │  Task Queue │   │
│  │ Jinja2   │   │  /api/*     │   │ asyncio     │   │
│  │ + HTMX   │   │             │   │ Queue       │   │
│  └────┬─────┘   └──────┬──────┘   └──────┬──────┘   │
│       │                │                 │           │
│       └────────────────┼─────────────────┘           │
│                        │                             │
│         ┌──────────────┼──────────────┐              │
│         ▼              ▼              ▼              │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐       │
│  │ LLM Service│ │Video Service│ │ Workflow   │       │
│  │ chat/      │ │ videogen/   │ │ Orchestrator│      │
│  │ completions│ │ generate    │ │            │       │
│  └─────┬──────┘ └──────┬─────┘ └─────┬──────┘       │
│        │               │             │               │
│        └───────┬───────┘             │               │
│                │                     │               │
│         ┌──────▼──────┐     ┌───────▼──────┐        │
│         │    SQLite   │     │ File Storage │        │
│         │  data.db    │     │ uploads/     │        │
│         └─────────────┘     │ outputs/     │        │
│                             └──────────────┘        │
└──────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌──────────────────────────────────────────────────────┐
│                 SophNet 算力平台                       │
│                                                      │
│  /v1/chat/completions              /projects/easyllms│
│  (LLM 文本/视觉)                    /videogenerator/  │
│                                     /generate         │
│                                     /query            │
└──────────────────────────────────────────────────────┘
```

### 2.2 核心数据流

```
用户上传图片 + 填写规格
        │
        ▼  POST /api/tasks → 返回 task_id，后台异步执行
┌─────────────────────┐
│ Step 1: 图片分析     │  model: DeepSeek-V4-Flash-Vision-Exp
│ Vision 模型识别：    │  POST /v1/chat/completions
│ 品类/材质/风格/卖点  │  (带 image_url 的 multimodal 请求)
└─────────┬───────────┘
          ▼ result.image_analysis → step 2 输入
┌─────────────────────┐
│ Step 2: 宣传文案生成  │  model: 用户选择 (DeepSeek/GLM/Kimi)
│ 标题、短描述、       │  POST /v1/chat/completions
│ 营销提示词(Prompt)   │  (纯文本，含上一步分析结果)
│ 用于生成图片/视频    │
└─────────┬───────────┘
          ▼ result.promo_texts → step 3 输入
┌─────────────────────┐
│ Step 3: 分镜头脚本    │  model: 用户选择
│ 5-8个分镜头：        │  POST /v1/chat/completions
│ - 场景描述           │  (纯文本，结构化输出)
│ - 运镜方式           │
│ - 时间/节奏          │
│ - 英文 prompt(供视频)│
└─────────┬───────────┘
          ▼ result.storyboard → step 4 输入
┌─────────────────────┐
│ Step 4: 视频生成      │  model: WAN2.7 / HappyHorse-1.1-i2v
│ 每个分镜头可选生成：  │  POST /videogenerator/generate
│ - 提交异步生成任务    │  → 获取 sophnet_task_id
│ - 轮询任务状态        │  GET /videogenerator/query
│ - 完成 → 下载视频     │
└─────────────────────┘
```

---

## 3. SophNet API 集成

### 3.1 LLM 调用（OpenAI 兼容）

**Endpoint**: `POST https://www.sophnet.com/api/open-apis/v1/chat/completions`
**Auth**: `Authorization: Bearer YOUR_API_KEY`

```json
{
    "model": "DeepSeek-V4-Flash-Vision-Exp",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
                {"type": "text", "text": "分析这个产品图片"}
            ]
        }
    ],
    "stream": false,
    "temperature": 0.7
}
```

### 3.2 视频生成

**生成 Endpoint**: `POST https://www.sophnet.com/api/open-apis/projects/easyllms/videogenerator/generate`
**查询 Endpoint**: `GET https://www.sophnet.com/api/open-apis/projects/easyllms/videogenerator/query?task_id={id}`

```json
{
    "model": "happyhorse-1.1-i2v",
    "content": [
        {
            "type": "image_url",
            "role": "first_frame",
            "image_url": {"url": "https://example.com/reference.jpg"}
        },
        {
            "type": "text",
            "text": "让图片中的角色动起来"
        }
    ],
    "parameters": {
        "duration": 5,
        "resolution": "720P"
    }
}
```

**查询响应预期格式**（轮询用）:
```json
{
    "status": "processing" | "completed" | "failed",
    "result": {"video_url": "https://..."} 
}
```

### 3.3 错误处理

- 所有 SophNet API 调用设 120s 超时
- LLM 调用失败：自动重试 2 次，间隔 3 秒
- 视频生成轮询：每 5 秒一次，最多轮询 120 次（10 分钟），超时标记 failed
- 错误信息写入数据库，前端可查看和重试

---

## 4. 数据模型

### 4.1 数据库表结构（SQLite）

**tasks（主任务表）**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | UUID |
| status | TEXT | pending/analyzing/writing/storyboard/generating_video/completed/failed |
| image_paths | JSON | 上传的图片本地路径数组 |
| specs | JSON | 用户填写的产品规格 {"品类":"","材质":"",...} |
| llm_model | TEXT | 选择的文本模型 |
| video_model | TEXT | 选择的视频模型 |
| result | JSON | 完整输出（见下方结构） |
| error_message | TEXT | 失败原因 |
| created_at | TEXT | ISO 8601 |
| updated_at | TEXT | ISO 8601 |

**result JSON 结构**：
```json
{
    "image_analysis": "分析文本...",
    "promo_texts": {
        "title": "标题",
        "short_description": "短描述",
        "selling_points": ["卖点1", "卖点2"],
        "promotional_prompt": "生图/生视频用prompt",
        "marketing_copy": "完整营销文案"
    },
    "storyboard": [
        {
            "shot_number": 1,
            "duration_sec": 3,
            "scene_description": "场景描述",
            "camera_movement": "运镜方式",
            "cn_prompt": "中文提示词",
            "en_prompt": "English prompt for video generation",
            "narration": "旁白文本"
        }
    ],
    "videos": [
        {"shot_index": 0, "path": "outputs/xxx.mp4", "status": "completed"}
    ]
}
```

**video_tasks（视频子任务表）**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | UUID |
| task_id | TEXT FK | 关联主任务 |
| shot_index | INT | 对应分镜头编号 |
| prompt | TEXT | 视频生成 prompt |
| input_image | TEXT | 图生视频的输入图 |
| video_path | TEXT | 输出视频本地路径 |
| status | TEXT | pending/processing/completed/failed |
| sophnet_task_id | TEXT | SophNet 平台返回的任务 ID |
| created_at | TEXT | ISO 8601 |
| updated_at | TEXT | ISO 8601 |

**config（配置表）**
| 字段 | 类型 | 说明 |
|------|------|------|
| key | TEXT PK | 配置名 |
| value | TEXT | 配置值 |
| updated_at | TEXT | ISO 8601 |

预设配置项：`api_key`, `preferred_llm_model`, `preferred_video_model`

---

## 5. API 设计

### 5.1 REST API

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/tasks` | 创建新任务（multipart: 图片+规格JSON），返回 task_id |
| GET | `/api/tasks` | 任务列表，支持 `?status=` 筛选和 `?page=` 分页 |
| GET | `/api/tasks/{id}` | 任务详情，含完整 result |
| DELETE | `/api/tasks/{id}` | 删除任务及关联文件 |
| POST | `/api/tasks/{id}/retry` | 手动重试失败任务 |
| GET | `/api/tasks/{id}/videos/{shot_index}` | 下载单个视频 |
| GET | `/api/config` | 获取配置 |
| POST | `/api/config` | 保存配置 |

### 5.2 页面路由

| 路由 | 页面 | 说明 |
|------|------|------|
| GET `/` | index.html | 主页：上传图片、填规格、提交任务 |
| GET `/tasks` | tasks.html | 任务列表 |
| GET `/tasks/{id}` | task_detail.html | 任务详情：文案、脚本、视频预览 |
| GET `/settings` | settings.html | 设置：API Key、默认模型 |

---

## 6. 前端设计

### 6.1 技术方案

- Jinja2 服务端模板渲染
- HTMX 实现无刷新交互（表单提交、状态轮询、局部刷新）
- Pico.css 提供基础样式，`static/style.css` 做自定义
- 零 JavaScript 框架依赖

### 6.2 页面说明

**主页 — 任务创建**
- 拖拽/点击上传产品图（支持多张）
- 图片缩略图预览
- 规格表单：品类、材质、风格、目标人群、尺寸/颜色等（动态 key-value）
- LLM 模型下拉选择、视频模型下拉选择
- "开始生成" 按钮 → POST /api/tasks → 跳转到任务详情页

**任务列表页**
- 表格形式：缩略图、状态标签、创建时间
- HTMX polling 或手动刷新更新状态
- 点击进入详情

**任务详情页**
- 进度条（当前阶段高亮）
- 各阶段输出卡片：图片分析→文案→脚本→视频
- 视频预览/下载
- HTMX 自动轮询（任务未完成时每 3 秒刷新）
- 失败时显示错误信息 + 重试按钮

**设置页**
- API Key 输入框（密码类型）
- 默认模型选择
- 保存 → POST /api/config

### 6.3 交互细节

- 任务提交后立即跳转详情页，显示 loading 和当前阶段
- 详情页 HTMX 轮询：`hx-get="/api/tasks/{id}?partial=1" hx-trigger="every 3s"`
- 任务完成后停止轮询
- 视频可直接在页面内 `<video>` 标签预览

---

## 7. 目录结构

```
dianshang/
├── app.py                    # FastAPI 应用入口，启动 uvicorn
├── settings.py               # 全局配置 (环境变量、默认值)
├── models.py                 # SQLAlchemy 数据模型
├── database.py               # 数据库初始化 & session 管理
├── routers/
│   ├── __init__.py
│   ├── tasks.py              # /api/tasks 路由
│   ├── config.py             # /api/config 路由
│   └── pages.py              # 页面路由 (Jinja2 渲染)
├── services/
│   ├── __init__.py
│   ├── sophnet_client.py     # SophNet HTTP 客户端封装
│   ├── llm_service.py        # Prompt 链 & LLM 调用
│   ├── video_service.py      # 视频生成 & 轮询
│   └── workflow.py           # 主流程编排 (asyncio)
├── templates/
│   ├── base.html             # 公共布局 (含 HTMX + Pico.css CDN)
│   ├── index.html            # 主页 — 创建任务
│   ├── tasks.html            # 任务列表
│   ├── task_detail.html      # 任务详情（含结果卡片 + 视频）
│   └── settings.html         # 设置页
├── static/
│   └── style.css             # 自定义样式
├── uploads/                  # 上传的图片（运行时创建）
├── outputs/                  # 生成的视频（运行时创建）
├── data.db                   # SQLite 数据库（运行时创建）
├── requirements.txt
├── .env.example              # 环境变量示例
├── .gitignore
└── README.md
```

---

## 8. Prompt 链设计

### 8.1 图片分析 Prompt

```
你是一个电商产品分析专家。请分析以下产品图片，输出 JSON：
{
  "category": "产品品类",
  "material": "材质",
  "style": "风格",
  "color_scheme": "配色方案",
  "target_audience": "目标人群",
  "key_features": ["卖点1", "卖点2", "卖点3"],
  "visual_highlights": "视觉亮点描述",
  "suggested_shooting_style": "建议拍摄风格"
}
```

### 8.2 宣传文案生成 Prompt

```
你是一个顶级的电商文案策划。根据以下产品分析结果和规格参数，生成淘宝店铺的宣传内容：

产品分析：{image_analysis}
产品规格：{specs}

请输出 JSON：
{
  "title": "吸引人的商品标题（含核心卖点关键词，30字以内）",
  "short_description": "一句话卖点描述",
  "selling_points": ["卖点详情1", "卖点详情2", ...],
  "promotional_prompt": "用于AI生图的提示词（中英双语，详细描述产品拍摄场景、光线、构图）",
  "marketing_copy": "完整的详情页营销文案（200-300字）"
}
```

### 8.3 分镜头脚本 Prompt

```
你是一个专业的广告导演。基于以下产品信息和宣传文案，设计一个 {duration} 秒的商品展示视频分镜头脚本。

产品信息：{product_info}
宣传文案：{promo_texts}

请输出 5-8 个分镜头，每个分镜头格式：
{
  "shot_number": 1,
  "duration_sec": 3,
  "scene_description": "中文场景描述（构图、主体、背景、氛围）",
  "camera_movement": "运镜方式（推/拉/摇/移/固定等）",
  "cn_prompt": "适合视频生成模型的中文提示词",
  "en_prompt": "English prompt suitable for AI video generation (detailed, visual, include motion description)",
  "narration": "该镜头的配音/旁白文本"
}

要求：
- 整体节奏流畅，适合商品展示
- 每个分镜头的 en_prompt 要具体、可视化，包含动作描述
- 考虑视频模型的提示词最佳实践
```

### 8.4 视频生成 Prompt 构建

在调用视频模型前，将分镜头 prompt 结合产品图片构建：

- **HappyHorse (图生视频)**：content 中 `image_url` 放产品图，`text` 放 `en_prompt`（或 `cn_prompt`）
- **WAN2.7**：同样格式，平台会根据模型能力处理

---

## 9. 核心实现要点

### 9.1 任务异步执行

使用 `asyncio.create_task` 实现后台任务执行，避免阻塞 HTTP 响应：

```python
# routers/tasks.py
@router.post("/api/tasks")
async def create_task(image: UploadFile, specs: str = Form(...), ...):
    task = await save_task_to_db(...)
    asyncio.create_task(workflow.execute(task.id))  # 后台执行
    return {"task_id": task.id}
```

### 9.2 图片处理

- 上传图片保存到 `uploads/{task_id}/` 目录
- 调用 Vision 模型前，将图片转 base64（小于 10MB 直传，大于则压缩）
- 本地图片在调用 SophNet 时转 data URL

### 9.3 视频轮询

```python
async def poll_video(sophnet_task_id: str, timeout: int = 600):
    for _ in range(timeout // 5):
        result = await client.query_video_task(sophnet_task_id)
        if result["status"] == "completed":
            return await download_video(result["result"]["video_url"])
        if result["status"] == "failed":
            raise VideoGenerationError(result.get("error"))
        await asyncio.sleep(5)
    raise TimeoutError("Video generation timeout")
```

---

## 10. 非功能需求

| 项目 | 方案 |
|------|------|
| 图片存储上限 | 每张图片 ≤ 20MB |
| 并发限制 | 同时最多 1 个活跃任务（个人工具） |
| 视频轮询超时 | 10 分钟 |
| 历史保留 | 不自动清理，用户手动删除 |
| API Key 安全 | 存 SQLite，不提交 git（.gitignore） |
| 无需认证 | 个人本机使用，无登录系统 |

---

## 11. 开发阶段

| 阶段 | 内容 | 预估耗时 |
|------|------|----------|
| Phase 1 | 基础骨架：FastAPI 项目结构、SQLite 模型、配置管理 | 0.5 天 |
| Phase 2 | LLM 服务：SophNet 客户端、图片分析+文案生成 Prompt 链 | 1 天 |
| Phase 3 | 视频服务：生成提交 + 轮询 + 下载 | 0.5 天 |
| Phase 4 | 主流程编排：Workflow 串联全流程 | 0.5 天 |
| Phase 5 | 前端页面：模板渲染 + HTMX 交互 | 1 天 |
| Phase 6 | 调试 & 打磨：边界处理、样式优化、README | 0.5 天 |
| **合计** | | **4 天** |