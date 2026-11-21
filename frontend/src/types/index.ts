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
