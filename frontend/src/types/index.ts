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
