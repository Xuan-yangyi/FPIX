import { HeroSection } from '../components/home/HeroSection'
import { ToolCard } from '../components/home/ToolCard'
import { TOOLS } from '../types'

export function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <HeroSection />

      <section className="mt-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TOOLS.slice(0, 3).map(tool => (
            <ToolCard key={tool.id} tool={tool} />
          ))}
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {TOOLS.slice(3, 5).map(tool => (
            <ToolCard key={tool.id} tool={tool} />
          ))}
        </div>
      </section>
    </div>
  )
}
