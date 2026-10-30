import { useEffect } from 'react'
import { EmptyState } from './empty.tsx'
import { CrateScene } from './pixel.tsx'
import { StudioHeader, type BuilderMode } from './switch.tsx'
import { Toasts } from './ui.tsx'

const COPY: Record<BuilderMode, { title: string; lead: string; way: string }> = {
  one: {
    title: 'A model with no volume.',
    lead: 'The 3D builder is still a box in a hard hat. It is very proud of the hat. It is also completely flat.',
    way: 'Until it grows a third dimension, the menu under Kaldr Studio has rooms that work. Sprite draws. Audio loops and babbles.',
  },
  batch: {
    title: 'A stack of empty boxes.',
    lead: 'A batch of models would stand here. The boxes are stacked with great care. They are also empty. One of them is wearing a hat.',
    way: 'Open the name under Kaldr Studio. Sprite Batch draws a pile. Audio Batch loops a pile. This room is still under construction.',
  },
}

export function Wip({ mode }: { mode: BuilderMode }) {
  const copy = COPY[mode]
  useEffect(() => {
    document.title = 'KALDR STUDIO'
  }, [])
  return (
    <div className="app">
      <Toasts />
      <StudioHeader builder="model" mode={mode} />
      <div className="wip-stage">
        <EmptyState kicker="Under construction" title={copy.title} art={<CrateScene />}>
          <p>{copy.lead}</p>
          <p>{copy.way}</p>
        </EmptyState>
      </div>
    </div>
  )
}
