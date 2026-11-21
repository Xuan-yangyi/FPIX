import { useNavigate } from 'react-router-dom'
import type { ToolInfo } from '../../types'

export function ToolCard({ tool }: { tool: ToolInfo }) {
  const navigate = useNavigate()

  return (
    <button
      onClick={() => navigate(`/tools/${tool.id}`)}
      className={`group relative flex flex-col items-start gap-3 rounded-2xl border border-border-card
                  bg-gradient-to-br ${tool.gradient} p-6 text-left
                  transition-all duration-300 hover:scale-[1.02] hover:border-border-glow
                  hover:shadow-[0_0_30px_rgba(99,102,241,0.1)]`}
    >
      <span className="text-3xl">{tool.icon}</span>
      <h3 className="text-lg font-semibold text-text-primary">{tool.title}</h3>
      <p className="text-sm text-text-secondary">{tool.description}</p>
    </button>
  )
}
