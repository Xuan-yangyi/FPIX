import { Download, RefreshCw, Sparkles, Image as ImageIcon } from 'lucide-react'
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
    <div className="space-y-5">
      {/* Progress */}
      {!done && stage && stage !== 'connected' && (
        <div className="glass rounded-2xl p-5 space-y-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
              <Sparkles size={16} className="text-accent animate-pulse" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-text-primary truncate">{message}</p>
              {total > 0 && (
                <p className="text-xs text-text-secondary">{current} / {total}</p>
              )}
            </div>
          </div>

          {total > 0 && (
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-primary/50">
              <div
                className="h-full rounded-full bg-gradient-to-r from-accent to-purple-500 transition-all duration-700 ease-out"
                style={{ width: `${(current / total) * 100}%` }}
              />
            </div>
          )}

          {total === 0 && (
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-primary/50">
              <div className="h-full w-1/3 rounded-full bg-gradient-to-r from-accent to-purple-500 animate-shimmer relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-5">
          <p className="text-sm text-red-400">{error}</p>
          <button onClick={onRetry}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-red-500/20 px-4 py-2 text-sm text-red-400
                             hover:bg-red-500/10 hover:text-red-300 transition-colors">
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
        <div className="glass rounded-2xl p-12 flex flex-col items-center justify-center text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/5 mb-4">
            <ImageIcon size={28} className="text-text-secondary/40" />
          </div>
          <p className="text-sm text-text-secondary">生成结果将在这里展示</p>
          <p className="mt-1 text-xs text-text-secondary/50">上传图片并配置参数后，点击"开始生成"</p>
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
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-accent to-purple-500 px-5 py-2.5
                       text-sm font-medium text-white shadow-[0_0_20px_rgba(99,102,241,0.3)]
                       hover:shadow-[0_0_30px_rgba(99,102,241,0.5)] transition-all duration-300"
          >
            <Download size={16} /> 下载全部
          </button>
        </div>
      )}
    </div>
  )
}