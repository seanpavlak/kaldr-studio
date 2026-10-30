import type { ReactNode } from 'react'
import { AudioLines, Box, Boxes, Image, Images, ListMusic, Music } from 'lucide-react'
import { DropdownNavigation, type DropdownNavItem } from '@/components/ui/dropdown-navigation.tsx'
import { Logo } from './pixel.tsx'
import { SoundToggle } from './ui.tsx'

export type BuilderId = 'sprite' | 'music' | 'model'
export type BuilderMode = 'one' | 'batch'

const PAGES = [
  { builder: 'sprite', mode: 'one', href: '/', label: 'Sprite Builder · Single' },
  { builder: 'sprite', mode: 'batch', href: '/batch', label: 'Sprite Builder · Batch' },
  { builder: 'music', mode: 'one', href: '/music', label: 'Audio Builder · Music' },
  { builder: 'music', mode: 'batch', href: '/music/batch', label: 'Audio Builder · Batch' },
  { builder: 'model', mode: 'one', href: '/3d', label: '3D Model Builder · Single' },
  { builder: 'model', mode: 'batch', href: '/3d/batch', label: '3D Model Builder · Batch' },
] as const satisfies readonly { builder: BuilderId; mode: BuilderMode; href: string; label: string }[]

const BUILDER_MENU: DropdownNavItem['subMenus'] = [
  {
    title: 'Sprite',
    items: [
      { label: 'Single', description: 'A single sprite', icon: Image, href: '/' },
      { label: 'Batch', description: 'A batch of sprites', icon: Images, href: '/batch' },
    ],
  },
  {
    title: 'Audio',
    items: [
      { label: 'Beep speech', description: 'Letter blips, no singer', icon: AudioLines, href: '/music/speech' },
      { label: 'Music', description: 'One loop, no vocals', icon: Music, href: '/music' },
      { label: 'Batch', description: 'A pile of loops', icon: ListMusic, href: '/music/batch' },
    ],
  },
  {
    title: '3D',
    items: [
      { label: 'Single', description: 'WIP', icon: Box, href: '/3d' },
      { label: 'Batch', description: 'WIP', icon: Boxes, href: '/3d/batch' },
    ],
  },
]

export function StudioHeader({ builder, mode, label, children }: { builder: BuilderId; mode: BuilderMode; label?: string; children?: ReactNode }) {
  const current = PAGES.find((page) => page.builder === builder && page.mode === mode) ?? PAGES[0]
  return (
    <header>
      <div className="brand">
        <a className="logo-link" href="/" aria-label="Kaldr Studio home"><Logo /></a>
        <div className="brand-text">
          <p className="mark">Kaldr Studio</p>
          <DropdownNavigation navItems={[{ id: 1, label: label ?? current.label, subMenus: BUILDER_MENU }]} />
        </div>
      </div>
      <div className="header-end">
        {children}
        <SoundToggle />
      </div>
    </header>
  )
}
