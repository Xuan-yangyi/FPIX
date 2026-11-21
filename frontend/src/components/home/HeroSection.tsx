import { useNavigate } from 'react-router-dom'
import { ArrowRight, Zap, Shield, Globe } from 'lucide-react'

const features = [
  { icon: Zap, label: '秒级生成' },
  { icon: Shield, label: '专业品质' },
  { icon: Globe, label: '多平台适配' },
]

export function HeroSection() {
  const navigate = useNavigate()

  return (
    <section className="relative py-24 sm:py-32 lg:py-40 text-center">
      {/* Badge */}
      <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-border-glow bg-accent-glow px-4 py-1.5 animate-pulse">
        <span className="h-2 w-2 rounded-full bg-accent" />
        <span className="text-xs text-accent">AI 驱动 · SophNet 引擎</span>
      </div>

      {/* Headline */}
      <h1 className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
        <span className="bg-gradient-to-r from-white via-text-primary to-accent bg-clip-text text-transparent">
          你的 AI 电商创意工作台
        </span>
      </h1>

      {/* Subtitle */}
      <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-text-secondary sm:text-xl">
        从商品图到全套素材，AI 自动完成白底图、场景图、模特图、带货视频的专业制作
      </p>

      {/* CTA */}
      <div className="mt-10 flex items-center justify-center gap-4">
        <button
          onClick={() => navigate('/tools/product_set')}
          className="group inline-flex items-center gap-2 rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-white
                     shadow-[0_0_30px_rgba(99,102,241,0.3)] hover:shadow-[0_0_50px_rgba(99,102,241,0.5)]
                     transition-all duration-300 hover:scale-[1.02]"
        >
          开始创作
          <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
        </button>

        <button
          onClick={() => navigate('/tools/video')}
          className="rounded-xl border border-border-card bg-white/5 px-6 py-3 text-sm font-medium text-text-primary
                     hover:border-border-glow hover:bg-white/10 transition-all duration-300"
        >
          体验 AI 视频
        </button>
      </div>

      {/* Feature badges */}
      <div className="mt-16 flex items-center justify-center gap-8">
        {features.map(({ icon: Icon, label }) => (
          <div key={label} className="flex items-center gap-2 text-sm text-text-secondary">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
              <Icon size={15} className="text-accent" />
            </div>
            {label}
          </div>
        ))}
      </div>

      {/* Decorative bottom line */}
      <div className="mt-20 mx-auto h-px w-64 bg-gradient-to-r from-transparent via-border-card to-transparent" />
    </section>
  )
}