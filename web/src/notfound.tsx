import { useEffect } from 'react'
import { ArrowLeft } from 'lucide-react'
import { EmptyState } from './empty.tsx'
import { LostScene } from './pixel.tsx'
import { StudioHeader } from './switch.tsx'
import { Toasts } from './ui.tsx'

export function NotFound() {
  useEffect(() => {
    document.title = 'Lost · KALDR STUDIO'
  }, [])
  return (
    <div className="app">
      <Toasts />
      <StudioHeader builder="sprite" mode="one" label="Nowhere in particular" />
      <div className="wip-stage">
        <EmptyState kicker="404" title="Blobert is lost." art={<LostScene />}>
          <p>This page wandered off, or it was never here at all. Blobert checked twice. He also checked under the sign.</p>
          <p>The menu under Kaldr Studio still knows the way to every room.</p>
          <div className="lost-links">
            <a className="make shine" href="/"><ArrowLeft aria-hidden="true" /> Back to Sprite</a>
            <a className="ghost" href="/music">Audio</a>
          </div>
        </EmptyState>
      </div>
    </div>
  )
}
