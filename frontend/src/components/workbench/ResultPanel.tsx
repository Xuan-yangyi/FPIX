import { Download, RefreshCw } from 'lucide-react'
import type { ResultImage } from '../../types'
import { ImageGallery } from './ImageGallery'

interface Props {
  results: ResultImage[]
  previewUrls: string[]
  stage: string
  message: string
  current: number
  total: number
  done: boolean
  error: string | null
  onRetry: () => void
}

export function ResultPanel({ results, previewUrls, stage, message, current, total, done, error, onRetry }: Props) {
  const hasContent = results.length > 0 || previewUrls.length > 0

  return (
    <div className="space-y-4">
      {/* Progress */}
      {!done && stage && stage !== 'connected' && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-text-secondary">{message}</span>
            {total > 0 && (
              <span className="text-accent">{current}/{total}</span>
            )}
          </div>
          {total > 0 && (
            <div className="h-1 w-full overflow-hidden rounded-full bg-bg-card">
              <div
                className="h-full rounded-full bg-accent transition-all duration-500"
                style={{ width: `${(current / total) * 100}%` }}
              />
            </div>
          )}
          {total === 0 && (
            <div className="h-1 w-full overflow-hidden rounded-full bg-bg-card">
              <div className="h-full w-1/3 animate-pulse rounded-full bg-accent" />
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <p className="text-sm text-red-400">{error}</p>
          <button onClick={onRetry}
                  className="mt-2 inline-flex items-center gap-1.5 text-sm text-red-400 hover:text-red-300">
            <RefreshCw size={14} /> 重试
          </button>
        </div>
      )}

      {/* Results */}
      {hasContent && (
        <ImageGallery images={results} previewUrls={previewUrls} />
      )}

      {/* Empty state */}
      {!hasContent && !stage && (
        <div className="flex flex-col items-center justify-center py-16 text-text-secondary">
          <p className="text-sm">上传图片并配置参数后开始生成</p>
        </div>
      )}

      {/* Download all */}
      {done && results.length > 0 && (
        <div className="flex justify-end">
          <button
            onClick={() => results.forEach(r => {
              const a = document.createElement('a')
              a.href = r.path
              a.download = ''
              a.click()
            })}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm text-white
                       hover:bg-accent/90 transition-colors"
          >
            <Download size={16} /> 下载全部
          </button>
        </div>
      )}
    </div>
  )
}
