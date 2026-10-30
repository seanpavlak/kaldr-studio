import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { UNKNOWN_LIMIT, UNLIMITED_KEY } from './money.ts'

type KeyStatus = { saved?: boolean; hint?: string; limited?: boolean | null }

export function useKey() {
  const [keyHint, setKeyHint] = useState('')
  const [keyDraft, setKeyDraft] = useState('')
  const [editingKey, setEditingKey] = useState(false)
  const keySaved = Boolean(keyHint)
  const keyLocked = keySaved && !editingKey

  useEffect(() => {
    let gone = false
    fetch('/openrouter-key')
      .then((res) => (res.ok ? res.json() : null))
      .then((body: KeyStatus | null) => {
        if (gone || !body?.saved || !body.hint) return
        setKeyHint(body.hint)
        fetch('/openrouter-key/limit')
          .then((res) => (res.ok ? res.json() : null))
          .then((limitBody: { limited?: boolean | null } | null) => {
            if (!gone && limitBody?.limited === false) toast.warning(UNLIMITED_KEY)
          })
          .catch(() => {})
      })
      .catch(() => {})
    return () => { gone = true }
  }, [])

  async function saveKey() {
    const key = keyDraft.trim()
    if (!key) return
    try {
      const res = await fetch('/openrouter-key', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      })
      const body = await res.json().catch(() => ({})) as KeyStatus & { error?: string }
      if (!res.ok || !body.hint) throw new Error(body.error || 'Could not save that key.')
      setKeyHint(body.hint)
      setKeyDraft('')
      setEditingKey(false)
      if (body.limited === false) toast.warning(UNLIMITED_KEY)
      else if (body.limited == null) toast.warning(UNKNOWN_LIMIT)
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Could not save that key.')
    }
  }

  function onKeyAction() {
    if (keyLocked) {
      setEditingKey(true)
      setKeyDraft('')
      return
    }
    void saveKey()
  }

  return { keyHint, keyDraft, setKeyDraft, editingKey, setEditingKey, keySaved, keyLocked, onKeyAction }
}

export function KeyField({ api }: { api: ReturnType<typeof useKey> }) {
  const keyInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (api.editingKey) keyInputRef.current?.focus()
  }, [api.editingKey])

  return (
    <>
      <div className="label-row">
        <label htmlFor="openrouter-key">OpenRouter key</label>
        <span className="info">
          <button type="button" className="info-btn" aria-label="Usage limit" aria-describedby="key-limit-tip">i</button>
          <span className="info-tip" id="key-limit-tip" role="tooltip">
            <span className="info-card">
              We recommend a usage limit for safety.{' '}
              <a href="https://openrouter.ai/settings/keys" target="_blank" rel="noopener">OpenRouter keys</a>
            </span>
          </span>
        </span>
      </div>
      <div className="key-row">
        <input
          ref={keyInputRef}
          id="openrouter-key"
          type={api.keyLocked ? 'text' : 'password'}
          autoComplete="off"
          spellCheck={false}
          placeholder="sk-or-v1-…"
          disabled={api.keyLocked}
          value={api.keyLocked ? api.keyHint : api.keyDraft}
          onChange={(event) => api.setKeyDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Escape' && api.editingKey) {
              event.preventDefault()
              api.setEditingKey(false)
              api.setKeyDraft('')
              return
            }
            if (event.key !== 'Enter') return
            event.preventDefault()
            api.onKeyAction()
          }}
        />
        <button type="button" disabled={!api.keyLocked && !api.keyDraft.trim()} onClick={api.onKeyAction}>
          {api.keySaved ? 'Update' : 'Save'}
        </button>
      </div>
    </>
  )
}
