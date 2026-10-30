import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import BatchApp from './Batch.tsx'
import MusicApp from './Music.tsx'
import { Privacy, Terms } from './legal.tsx'
import { NotFound } from './notfound.tsx'
import { Wip } from './wip.tsx'
import './index.css'

const path = window.location.pathname.replace(/\/$/, '') || '/'

const PAGES: Record<string, ReactNode> = {
  '/': <App />,
  '/index.html': <App />,
  '/terms': <Terms />,
  '/privacy': <Privacy />,
  '/batch': <BatchApp />,
  '/music': <MusicApp mode="one" />,
  '/music/speech': <MusicApp mode="speech" />,
  '/music/batch': <MusicApp mode="batch" />,
  '/3d': <Wip mode="one" />,
  '/3d/batch': <Wip mode="batch" />,
}

const page = PAGES[path] ?? <NotFound />

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {page}
  </StrictMode>,
)
