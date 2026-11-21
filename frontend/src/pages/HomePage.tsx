import { HeroSection } from '../components/home/HeroSection'
import { ToolCard } from '../components/home/ToolCard'
import { TOOLS } from '../types'

export function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-6">
      <HeroSection />

      {/* Tools section */}
      <section className="pb-24">
        <div className="mb-10 text-center">
          <h2 className="text-2xl font-bold text-text-primary">选择工具，开始创作</h2>
          <p className="mt-2 text-sm text-text-secondary">5 种 AI 工具，覆盖电商素材全流程</p>
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {TOOLS.slice(0, 3).map(tool => (
            <ToolCard key={tool.id} tool={tool} />
          ))}
        </div>
        <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
          {TOOLS.slice(3, 5).map(tool => (
            <ToolCard key={tool.id} tool={tool} />
          ))}
        </div>
      </section>
    </div>
  )
}