import { useState, useEffect } from 'react'
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
        setPreviewUrls(prev => [...prev, data.preview_url!])
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
