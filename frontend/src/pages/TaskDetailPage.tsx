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
