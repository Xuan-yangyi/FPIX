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
