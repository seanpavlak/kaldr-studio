import { useEffect, useRef, type RefObject } from 'react'

/** Cmd or Ctrl + Enter submits the rail form from anywhere on the page. */
export function useSubmitShortcut(form: RefObject<HTMLFormElement | null>) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Enter' || !(event.metaKey || event.ctrlKey)) return
      if (!form.current) return
      event.preventDefault()
      form.current.requestSubmit()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [form])
}

/** Fires once each time `done` flips from false to true. */
export function useOnDone(done: boolean, run: () => void) {
  const was = useRef(done)
  const latest = useRef(run)
  useEffect(() => {
    latest.current = run
  })
  useEffect(() => {
    if (done && !was.current) latest.current()
    was.current = done
  }, [done])
}
