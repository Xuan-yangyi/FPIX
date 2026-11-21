import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Image, Video, Wand2, Scissors, User, Settings as Gear } from 'lucide-react'
import { Logo } from './Logo'

const navItems = [
  { to: '/', label: '首页', icon: Image },
  { to: '/tools/product_set', label: '商品套图', icon: Image },
  { to: '/tools/remove_bg', label: 'AI 抠图', icon: Scissors },
  { to: '/tools/model', label: 'AI 模特', icon: User },
  { to: '/tools/video', label: 'AI 视频', icon: Video },
  { to: '/tools/edit', label: 'AI 编辑', icon: Wand2 },
]

export function Navbar() {
  const location = useLocation()
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 h-16 border-b transition-all duration-300
                  ${scrolled
                    ? 'border-border-card bg-bg-primary/90 shadow-[0_1px_20px_rgba(0,0,0,0.3)]'
                    : 'border-transparent bg-transparent'}`}
    >
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-6">
        {/* Brand */}
        <Link to="/" className="flex items-center gap-2.5 group">
          <Logo size={30} />
          <span className="text-lg font-bold bg-gradient-to-r from-accent to-purple-400 bg-clip-text text-transparent">
            FPIX
          </span>
        </Link>

        {/* Nav links */}
        <div className="hidden md:flex items-center gap-0.5">
          {navItems.map(({ to, label, icon: Icon }) => {
            const active = to === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(to)
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm transition-all duration-200
                            ${active
                              ? 'text-text-primary bg-accent/10'
                              : 'text-text-secondary hover:text-text-primary hover:bg-white/5'}`}
              >
                <Icon size={15} />
                {label}
              </Link>
            )
          })}
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-2">
          <Link
            to="/settings"
            className="rounded-lg p-2 text-text-secondary hover:text-text-primary hover:bg-white/5 transition-all"
            title="设置"
          >
            <Gear size={18} />
          </Link>
        </div>
      </div>
    </nav>
  )
}