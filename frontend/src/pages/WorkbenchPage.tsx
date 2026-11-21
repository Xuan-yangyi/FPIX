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
