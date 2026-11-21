# PixPix-Style E-Commerce AI Image Generation Platform

**Date:** 2026-11-21
**Status:** Design Phase
**Branch:** master (will branch for implementation)

---

## 1. Overview

Transform the existing `dianshang` project from a single-purpose video generation tool into a PixPix-style multi-tool AI e-commerce design platform. Users can upload product images and generate complete listing materials: white-background images, scene images, detail shots, size charts, background-removed PNGs, model replacements, marketing videos, and AI-edited images.

### Core Principles

- **Workflow orchestration by code, not by LLM Agent** — Task decomposition is deterministic Python; LLMs only handle content generation (analysis, prompts).
- **Single backend, modern frontend** — Keep the mature FastAPI backend; replace the Jinja2/HTMX frontend with a React SPA.
- **Dark, polished, PixPix-like UI** — Tailwind CSS dark theme with gradient cards, glass effects, and Framer Motion micro-animations.
- **Real-time progress via SSE** — Users see each image appear as it's generated.

---

## 2. Architecture

```
dianshang/
├── backend/                    # FastAPI (existing, extended)
│   ├── services/
│   │   ├── workflow.py          # Extended: product_set, remove_bg, model, edit workflows
│   │   ├── llm_service.py       # Extended: new prompt templates for image generation
│   │   ├── sophnet_client.py   # Extended: image generation API methods
│   │   └── video_service.py    # Unchanged
│   ├── routers/
│   │   ├── tasks.py             # Extended: unified task creation + SSE progress
│   │   ├── pages.py             # Simplified: only serve SPA entry point
│   │   └── config.py            # Unchanged
│   ├── models.py                # Extended: workflow_type, params fields
│   ├── database.py              # Unchanged
│   └── app.py                   # Extended: CORS, static file serving, mount SPA
│
├── frontend/                    # React SPA (NEW)
│   ├── src/
│   │   ├── pages/               # HomePage, WorkbenchPage, TaskDetailPage
│   │   ├── components/          # Navbar, ToolCard, ImageUploader, ImageGallery, etc.
│   │   ├── hooks/               # useTaskProgress (SSE), useTaskCreate
│   │   ├── api/                 # fetch client
│   │   └── types/               # TypeScript types
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.ts
│
└── docs/superpowers/specs/      # Design documents
```

### Deployment Model

Single-process: FastAPI serves both `/api/*` routes and the built React SPA static files. No separate frontend server needed.

---

## 3. Data Model

### Task (extended)

| Field | Type | Description |
|-------|------|-------------|
| id | Text (PK) | UUID hex |
| status | Text | pending → processing → completed / failed |
| workflow_type | Text | `product_set`, `remove_bg`, `model`, `video`, `edit` |
| image_paths | Text (JSON) | Input image file paths |
| params | Text (JSON) | Workflow-specific parameters (platform, ratio, language, requirements, etc.) |
| result | Text (JSON) | Generated output (image/video paths, metadata) |
| error_message | Text | Error details if failed |
| created_at / updated_at | Text | ISO timestamps |

### VideoTask (unchanged)

Used only by the `video` workflow.

### Config (unchanged)

Key-value store for API keys and settings.

---

## 4. API Design

### Routes

```
POST   /api/upload                   # Multipart upload → { file_paths: [...] }
POST   /api/tasks                    # Create task → { task_id, status }
GET    /api/tasks/:id                # Get task status + result
GET    /api/tasks/:id/progress       # SSE stream { stage, current, total, preview_url? }
GET    /api/gallery                  # Recent completed tasks for homepage
```

### Task Creation Payload

```json
{
  "workflow_type": "product_set",
  "image_paths": ["uploads/xxx.jpg"],
  "params": {
    "platform": "amazon",
    "ratio": "1:1",
    "language": "zh",
    "image_types": ["white_bg", "scene", "selling_point", "detail", "size_chart"],
    "requirements": "清新高级风格，适合美妆品类"
  },
  "llm_model": "DeepSeek-V4-Flash-Vision-Exp",
  "image_model": "qwen-image-plus"
}
```

### SSE Progress Events

```json
// Stage transitions
{ "stage": "analyzing", "message": "正在分析商品..." }
{ "stage": "writing", "message": "正在生成场景描述..." }
{ "stage": "generating", "current": 1, "total": 8 }

// Image by image  
{ "stage": "generating", "current": 3, "total": 8, "preview_url": "/results/xxx/scene_1.png", "type": "scene" }

// Complete
{ "stage": "completed", "result_images": ["/results/xxx/white_bg.png", ...] }
```

---

## 5. Workflows

### 5.1 Product Set (`product_set`)

The core workflow. Generates 6-10 listing images from a single product photo.

```
Stage 1 — Image Analysis (DeepSeek-V4-Flash-Vision)
  Input:  Product photo (base64)
  Output: { category, material, style, color_scheme, texture_detail, lighting,
            key_features[], product_contour, keep_intact[] }

Stage 2 — Prompt Engineering (DeepSeek/GLM)
  Input:  Analysis JSON + platform + ratio + language + user requirements
  Output: Per-image prompts:
    { white_bg:     { cn_prompt, en_prompt, style_notes },
      scenes:       [{ cn_prompt, en_prompt, style_notes }],
      selling_point:{ cn_prompt, en_prompt, style_notes },
      detail:       { cn_prompt, en_prompt, style_notes },
      size_chart:   { cn_prompt, en_prompt, style_notes } }

Stage 3 — Batch Image Generation (Qwen-Image / Qwen-Image-Plus)
  Input:  Reference product image + individual prompts
  Output: 6-10 generated images
  Progress: SSE event per completed image

Stage 4 — Post-processing (optional, Qwen-Image-Edit-2509)
  - Fix any artifacts
  - Unify dimensions
  - Add watermark if requested
```

Image types per workflow:
- `white_bg`: Clean product display on white, multiple angles (1-2 images)
- `scene`: Lifestyle/product-in-use scene (2-4 images)
- `selling_point`: Core feature highlights with text overlay area (2-3 images)
- `detail`: Close-up texture/material shots (1-2 images)
- `size_chart`: Dimensions and structure diagram (1 image, smart-matched by category)

### 5.2 Remove Background (`remove_bg`)

```
Stage 1 — Background Removal (Qwen-Image-Edit-2509)
  Input:  Product photo
  Output: Transparent PNG

Stage 2 — White Background Variant
  Input:  Transparent PNG
  Output: White-background version
```

Output formats: transparent PNG, white background, or both.

### 5.3 AI Model (`model`)

```
Stage 1 — Image Analysis
  Identify: existing model/background/accessories

Stage 2 — Targeted Replacement (Qwen-Image-Edit-2509)
  Input:  Original image + replacement description
  Output: Multiple scene variants with new model/background
```

### 5.4 AI Video (`video`)

Existing workflow. Analysis → Promo Texts → Storyboard → Video Generation (happyhorse-1.1-i2v).

### 5.5 AI Edit (`edit`)

```
Stage 1 — Instruction Parsing (LLM)
  Input:  Natural language edit instruction
  Output: Structured edit parameters (target_region, action, style_ref)

Stage 2 — Image Editing (Qwen-Image-Edit-2509)
  Input:  Original image + structured edit parameters
  Output: Edited image
```

---

## 6. Frontend Design

### 6.1 Tech Stack

- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS 4 (styling)
- shadcn/ui (base components: Button, Dialog, Select, Progress, Tabs)
- Framer Motion (micro-animations: card hover, page transitions, stagger reveals)
- React Router v6 (client-side routing)

### 6.2 Design System — PixPix Dark Theme

```css
Colors:
  --bg-primary:     #0a0a0f   (deep dark blue-black)
  --bg-card:        #13131a   (card background)
  --bg-card-hover:  #1a1a24   (card hover)
  --accent:         #6366f1   (indigo purple-blue highlights)
  --text-primary:   #e4e4e7   (light gray-white)
  --text-secondary: #71717a   (muted gray)
  --border-subtle:  rgba(255,255,255,0.06)
  --border-card:    rgba(255,255,255,0.08)

Typography:
  - Geometric sans-serif (Inter for body, Bricolage Grotesque for headings)
  - Clean hierarchy with generous spacing

Visual signatures:
  - Dark backgrounds with subtle gradient cards
  - Glowing borders on hover
  - Glass/morphism effects (backdrop-blur)
  - Rounded corners on image containers
  - Card lift + scale(1.02) on hover
```

### 6.3 Component Tree

```
App
├── Layout
│   ├── Navbar
│   └── <Outlet />
│
├── HomePage (/)
│   ├── HeroSection
│   ├── ToolCardGrid
│   │   └── ToolCard (×5)
│   └── GallerySection
│       └── GalleryCard (×N)
│
├── WorkbenchPage (/tools/:type)
│   ├── ConfigPanel
│   │   ├── ImageUploader (drag & drop)
│   │   ├── WorkflowConfig (platform/ratio/language/type selects)
│   │   └── RequirementInput
│   └── ResultPanel
│       ├── ProgressBar
│       └── ImageGallery
│           └── ResultCard (per image)
│
├── TaskDetailPage (/task/:id)
│   ├── TaskStatus
│   ├── ImageGallery
│   └── DownloadAllButton
│
└── Common
    ├── ImageLightbox
    ├── LoadingSpinner
    └── EmptyState
```

### 6.4 Page Layouts

**Homepage:**
```
┌────────────────────────────────────────────────┐
│ [Logo]  AI图片 AI视频 AI编辑        [Settings] │  ← Navbar
├────────────────────────────────────────────────┤
│                                                │
│      你的 AI 电商创意工作台                      │  ← Hero
│  从商品图到全套素材，AI 自动完成                  │
│                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  商品套图  │ │  AI抠图   │ │  AI模特   │       │  ← Tool cards
│  └──────────┘ └──────────┘ └──────────┘       │     (5 cards, gradient backgrounds)
│  ┌──────────┐ ┌──────────┐                    │
│  │  AI视频   │ │  AI编辑   │                    │
│  └──────────┘ └──────────┘                    │
│                                                │
│  创作灵感 → [Gallery grid of recent results]    │  ← Gallery
└────────────────────────────────────────────────┘
```

**Workbench (left-right split):**
```
┌──────────────────────────────────────────────────┐
│ ← 返回    商品套图                                │
├──────────────────────┬───────────────────────────┤
│  Config Panel        │  Result Panel             │
│                      │                           │
│  📷 上传商品图        │  ┌────┐ ┌────┐ ┌────┐   │
│  [  Drop Zone  ]     │  │白底│ │场景│ │卖点│   │
│                      │  └────┘ └────┘ └────┘   │
│  平台: [亚马逊 ▼]     │  ┌────┐ ┌────┐ ┌────┐   │
│  比例: [1:1 ▼]      │  │详情│ │尺寸│ │场景│   │
│  语言: [中文 ▼]      │  └────┘ └────┘ └────┘   │
│                      │                           │
│  图类型:              │  [下载全部] [重新生成]     │
│  ☑ 白底图 ☑ 场景图   │                           │
│  ☑ 卖点图 ☑ 详情图   │                           │
│  ☑ 尺寸图             │                           │
│                      │                           │
│  补充要求: [______]   │                           │
│                      │                           │
│  [🚀 生成套装]        │                           │
└──────────────────────┴───────────────────────────┘
```

### 6.5 Key Interactions

**SSE Progress Hook (`useTaskProgress`):**
```typescript
function useTaskProgress(taskId: string) {
  // Returns: { stage, progress {current, total}, results[], previewUrls[] }
  // Connects to GET /api/tasks/:id/progress (EventSource)
  // Auto-closes on stage === "completed"
}
```

**Image Gallery Animation:**
- Images appear one by one with Framer Motion `staggerChildren: 0.15`
- Each ResultCard fades in + slides up
- Click to open ImageLightbox (overlay with full-res image, left/right nav, download button)

---

## 7. Model Capabilities Summary

| Model | Purpose | API |
|-------|---------|-----|
| DeepSeek-V4-Flash-Vision-Exp | Image analysis (vision) | SophNet chat/completions |
| DeepSeek/GLM-4-Flash | Prompt generation (text) | SophNet chat/completions |
| Qwen-Image | Text-to-image / image-to-image | SophNet image generation |
| Qwen-Image-Plus | Higher quality image generation | SophNet image generation |
| Qwen-Image-Edit-2509 | Background removal, inpainting, region editing | SophNet image edit |
| happyhorse-1.1-i2v | Image-to-video | SophNet video generation |

---

## 8. Implementation Phases

### Phase 1: Foundation (Week 1)
- Initialize React + Vite + Tailwind + shadcn/ui project in `frontend/`
- Build Layout, Navbar, and routing skeleton
- Implement dark theme design system
- Set up API client and proxy (`vite.config.ts` → proxy `/api` to FastAPI)

### Phase 2: Product Set Workflow (Week 1-2)
- Extend backend Task model with `workflow_type` and `params`
- Implement `product_set` workflow in `workflow.py`
- Add image generation API methods to `SophNetClient`
- Add SSE progress endpoint
- Build HomePage with ToolCard grid
- Build WorkbenchPage with ConfigPanel + ResultPanel
- Build ImageUploader, WorkflowConfig components

### Phase 3: Remove Background + AI Edit (Week 2)
- Implement `remove_bg` workflow (Qwen-Image-Edit-2509)
- Implement `edit` workflow (LLM parsing + Qwen-Image-Edit-2509)
- Add corresponding WorkflowConfig variants
- Build ImageGallery + ResultCard components

### Phase 4: AI Model + Polish (Week 3)
- Implement `model` workflow
- Build ImageLightbox component
- Add GallerySection to homepage (recent task results)
- Polish animations, transitions, loading states
- Mobile-responsive adjustments
- Error states and edge case handling

### Phase 5: Migration & Deploy (Week 3-4)
- Integrate existing video workflow into new frontend
- Update FastAPI to serve built React SPA
- Remove old Jinja2 templates (or keep as fallback)
- End-to-end testing
- Deploy

---

## 9. Trade-offs & Decisions

### Why not Next.js?
FastAPI already has a robust async workflow engine, SophNet client with retry logic, database layer, and file management. Rewriting in JavaScript would be wasted effort with no benefit — the React SPA only needs REST endpoints.

### Why not Claude Agent?
The workflows are deterministic: user selects a tool, fills in structured params, and clicks generate. An LLM Agent adds latency, cost, and non-determinism with no UX benefit. Code-based orchestration is faster, cheaper, and more reliable.

### Why SSE instead of WebSocket?
SSE is simpler, unidirectional (server → client), and sufficient for progress updates. WebSocket would be overkill — the client only subscribes to task progress, never sends messages mid-generation.

### Why not Tailwind component library (DaisyUI/Flowbite)?
Custom Tailwind gives pixel-level control to match PixPix's distinctive visual style. shadcn/ui provides accessible base components (Select, Dialog, Progress) without imposing a design system.

---

## 10. Open Questions

1. **SophNet Qwen-Image API**: Does it support reference image + text prompt as input? This is critical for maintaining product identity across generated images. Needs verification.
2. **Qwen-Image-Edit-2509 masking**: Does it accept mask inputs or is it instruction-based only? Affects precision of background removal and model replacement.
3. **Rate limits and billing**: What are the concurrency limits on SophNet for image generation? Affects how many parallel generations we can run.