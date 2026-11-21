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
