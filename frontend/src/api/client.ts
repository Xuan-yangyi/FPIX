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
    const res = await fetch(`${BASE}/tasks/upload`, { method: 'POST', body: form })
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
