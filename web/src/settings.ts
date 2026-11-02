import { useEffect, useRef } from 'react'

export type SettingsSection = 'sprite' | 'loop' | 'speech'

const SAVE_DELAY = 400

/**
 * Keeps one section of kaldr-settings.json in step with a builder's controls.
 * The saved values come back once on load, then every change is written behind a short delay.
 */
export function useSavedSettings<T>(section: SettingsSection, value: T, restore: (saved: T) => void) {
  const text = JSON.stringify(value)
  const first = useRef(text)
  const latest = useRef(text)
  const saved = useRef<string | null>(null)
  const restoreRef = useRef(restore)
  useEffect(() => {
    latest.current = text
    restoreRef.current = restore
  })

  useEffect(() => {
    let gone = false
    void fetch('/settings')
      .then((res) => (res.ok ? res.json() : null))
      .then((body: Partial<Record<SettingsSection, T>> | null) => {
        if (gone) return
        const stored = body?.[section]
        // Someone already moved a control while this loaded, so theirs stands.
        if (stored && latest.current === first.current) {
          saved.current = JSON.stringify(stored)
          restoreRef.current(stored)
        } else {
          saved.current = first.current
        }
      })
      .catch(() => { if (!gone) saved.current = first.current })
    return () => { gone = true }
  }, [section])

  useEffect(() => {
    if (saved.current === null || saved.current === text) return
    const timer = window.setTimeout(() => {
      saved.current = text
      void fetch('/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [section]: JSON.parse(text) }),
      }).catch(() => {})
    }, SAVE_DELAY)
    return () => window.clearTimeout(timer)
  }, [section, text])
}
