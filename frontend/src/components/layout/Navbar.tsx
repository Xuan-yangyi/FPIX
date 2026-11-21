import { Link } from 'react-router-dom'
import { Image, Video, Wand2 } from 'lucide-react'

const navItems = [
  { to: '/', label: 'AI 图片', icon: Image },
  { to: '/tools/video', label: 'AI 视频', icon: Video },
  { to: '/tools/edit', label: 'AI 编辑', icon: Wand2 },
]

export function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-16 border-b border-border-subtle bg-bg-primary/80 backdrop-blur-xl">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2">
          <span className="text-xl font-bold text-text-primary">电商AI</span>
        </Link>

        <div className="flex items-center gap-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-text-secondary
                         hover:text-text-primary hover:bg-bg-card transition-colors"
            >
              <Icon size={16} />
              {label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/settings"
            className="text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            设置
          </Link>
        </div>
      </div>
    </nav>
  )
}
