import { useCallback, useState } from 'react'
import { Upload, X, Image as ImageIcon } from 'lucide-react'

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
    <div className="glass rounded-2xl p-5 space-y-4">
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10">
          <ImageIcon size={14} className="text-accent" />
        </div>
        <span className="text-sm font-medium text-text-primary">上传商品图片</span>
        <span className="text-xs text-text-secondary ml-auto">{files.length}/9</span>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById('file-input')?.click()}
        className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8
                    transition-all duration-300 cursor-pointer
                    ${dragging
                      ? 'border-accent bg-accent/10 scale-[1.01]'
                      : 'border-border-card hover:border-border-glow hover:bg-white/[0.02]'}`}
      >
        <div className={`flex h-12 w-12 items-center justify-center rounded-full transition-colors
                         ${dragging ? 'bg-accent/20' : 'bg-white/5'}`}>
          <Upload size={20} className={dragging ? 'text-accent' : 'text-text-secondary'} />
        </div>
        <div className="text-center">
          <p className="text-sm text-text-secondary">
            {dragging ? '松开即可上传' : '拖拽图片到此处或点击上传'}
          </p>
          <p className="mt-1 text-xs text-text-secondary/50">最多 9 张，单张不超过 20MB</p>
        </div>
        <input
          id="file-input"
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={handleFileInput}
        />
      </div>

      {/* Thumbnails */}
      {files.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {files.map((f, i) => (
            <div key={i} className="group relative">
              <img
                src={URL.createObjectURL(f)}
                alt={f.name}
                className="h-16 w-16 rounded-lg object-cover ring-1 ring-white/10"
              />
              <button
                onClick={(e) => { e.stopPropagation(); removeFile(i) }}
                className="absolute -right-1.5 -top-1.5 rounded-full bg-bg-primary border border-border-card p-0.5
                           opacity-0 group-hover:opacity-100 transition-all hover:border-red-500/30"
              >
                <X size={12} className="text-text-secondary hover:text-red-400" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}