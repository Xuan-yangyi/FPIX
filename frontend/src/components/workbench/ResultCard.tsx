import { Download } from 'lucide-react'
import type { ResultImage } from '../../types'

interface Props {
  image: ResultImage
  onPreview: (path: string) => void
}

const typeLabels: Record<string, string> = {
  white_bg: '白底图',
  scene: '场景图',
  selling_point: '卖点图',
  detail: '详情图',
  size_chart: '尺寸图',
  transparent: '透明PNG',
  white_bg_out: '白底图',
  variant: '变体',
  edited: '编辑结果',
}

export function ResultCard({ image, onPreview }: Props) {
  const fullUrl = image.path

  return (
    <div className="group relative overflow-hidden rounded-xl border border-border-card bg-bg-card
                    transition-all duration-300 hover:border-border-glow hover:shadow-lg">
      <img
        src={fullUrl}
        alt={image.type}
        className="h-48 w-full object-cover cursor-pointer"
        onClick={() => onPreview(fullUrl)}
        loading="lazy"
      />
      <div className="flex items-center justify-between px-3 py-2">
        <span className="text-xs text-text-secondary">{typeLabels[image.type] || image.type}</span>
        <a
          href={fullUrl}
          download
          className="rounded p-1 text-text-secondary hover:text-text-primary transition-colors"
          onClick={e => e.stopPropagation()}
        >
          <Download size={14} />
        </a>
      </div>
    </div>
  )
}
