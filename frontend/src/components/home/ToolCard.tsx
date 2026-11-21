import { useNavigate } from 'react-router-dom'
import { ShoppingBag, Scissors, User, Video, PenTool, ArrowRight } from 'lucide-react'
import type { ToolInfo } from '../../types'

const iconMap: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  '🛍️': ShoppingBag,
  '✂️': Scissors,
  '👤': User,
  '▶️': Video,
  '🖌️': PenTool,
}

const colorMap: Record<string, string> = {
  product_set: 'from-indigo-500/30 to-purple-600/30 border-indigo-500/20 hover:shadow-indigo-500/10',
  remove_bg: 'from-emerald-500/30 to-teal-600/30 border-emerald-500/20 hover:shadow-emerald-500/10',
  model: 'from-orange-500/30 to-pink-600/30 border-orange-500/20 hover:shadow-orange-500/10',
  video: 'from-blue-500/30 to-cyan-600/30 border-blue-500/20 hover:shadow-blue-500/10',
  edit: 'from-rose-500/30 to-red-600/30 border-rose-500/20 hover:shadow-rose-500/10',
}

const iconColorMap: Record<string, string> = {
  product_set: 'text-indigo-400',
  remove_bg: 'text-emerald-400',
  model: 'text-orange-400',
  video: 'text-blue-400',
  edit: 'text-rose-400',
}

export function ToolCard({ tool }: { tool: ToolInfo }) {
  const navigate = useNavigate()
  const Icon = iconMap[tool.icon] || ShoppingBag

  return (
    <button
      onClick={() => navigate(`/tools/${tool.id}`)}
      className={`group relative flex flex-col items-start gap-4 rounded-2xl border bg-gradient-to-br
                  ${colorMap[tool.id] || colorMap.product_set}
                  p-6 text-left transition-all duration-500
                  hover:scale-[1.02] hover:-translate-y-1 hover:shadow-[0_8px_40px_rgba(0,0,0,0.3)]`}
    >
      {/* Icon */}
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/5 group-hover:bg-white/10 transition-colors">
        <Icon size={24} className={iconColorMap[tool.id] || 'text-accent'} />
      </div>

      {/* Text */}
      <div>
        <h3 className="text-lg font-semibold text-text-primary flex items-center gap-1.5">
          {tool.title}
          <ArrowRight size={16} className="opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300 text-text-secondary" />
        </h3>
        <p className="mt-1.5 text-sm leading-relaxed text-text-secondary">{tool.description}</p>
      </div>

      {/* Hover glow */}
      <div className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
           style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.1)' }} />
    </button>
  )
}