import { useEffect, useRef, useState, type FormEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Download, ImagePlus, Link2, Sparkles, X } from 'lucide-react'
import { toast } from 'sonner'
import { ThinkingOrb } from 'thinking-orbs'
import { EmptyState } from './empty.tsx'
import { celebrate, sfx } from './fx.ts'
import { KeyField, useKey } from './key.tsx'
import { budgetAllows, money } from './money.ts'
import { CongaScene } from './pixel.tsx'
import { ModelField, SpriteFields } from './sprite-controls.tsx'
import { StudioHeader } from './switch.tsx'
import { useOnDone, useSubmitShortcut } from './hooks.ts'
import { DEFAULT_RENDER, FALLBACK_MODEL, type Batch, type Job, type RenderSettings, type StudioModel } from './types.ts'
import { DropVeil, PayModal, Shortcut, Toasts } from './ui.tsx'

const MAX_BATCH = 20
const ORB = { queued: 'connecting', download: 'searching', redraw: 'weaving', pixelate: 'shaping', animate: 'breathing' } as const

const STAGE_TEXT: Record<string, string> = {
  queued: 'In line.',
  download: 'Fetching.',
  upload: 'Reading.',
  redraw: 'Redrawing.',
  pixelate: 'Pixelating.',
  animate: 'Animating.',
}

type QueueItem =
  | { id: string; kind: 'file'; file: File; name: string; preview: string }
  | { id: string; kind: 'url'; url: string }

async function readJson<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => ({})) as T & { error?: string }
  if (!res.ok) throw new Error(body.error || 'Could not reach the studio.')
  return body
}

export default function BatchApp() {
  const key = useKey()
  const [models, setModels] = useState<StudioModel[]>([])
  const [model, setModel] = useState(FALLBACK_MODEL.id)
  const [render, setRender] = useState<RenderSettings>(DEFAULT_RENDER)
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [urlDraft, setUrlDraft] = useState('')
  const [hot, setHot] = useState(false)
  const formRef = useRef<HTMLFormElement>(null)
  const stageRef = useRef<HTMLElement>(null)
  useSubmitShortcut(formRef)
  const [batch, setBatch] = useState<Batch | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [confirming, setConfirming] = useState<null | 'batch' | string>(null)
  const [nag, setNag] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const confirmRef = useRef<HTMLButtonElement>(null)

  const modelOptions = models.length ? models : [{ ...FALLBACK_MODEL, id: model }]
  const chosen = modelOptions.find((item) => item.id === model) ?? modelOptions[0]
  const billCount = queue.length
  const oneLabel = money(chosen.usd, chosen.estimate)
  const running = submitting || Boolean(batch?.items.some((item) => item.job?.status === 'running'))
  const successes = batch?.items.filter((item) => item.job?.status === 'done').length ?? 0
  const finished = batch?.items.filter((item) => item.job?.status === 'done') ?? []
  const settled = batch?.items.filter((item) => item.job && item.job.status !== 'running').length ?? 0
  const total = batch?.items.length ?? 0
  const allSettled = total > 0 && settled === total

  useOnDone(allSettled && successes > 0, () => celebrate(stageRef.current, 90 + successes * 6))

  useEffect(() => {
    document.title = 'KALDR STUDIO'
    let gone = false
    fetch('/models')
      .then((res) => (res.ok ? res.json() : null))
      .then((body: { models?: StudioModel[] } | null) => {
        if (!gone && body?.models?.length) setModels(body.models)
      })
      .catch(() => {})
    return () => { gone = true }
  }, [])

  useEffect(() => {
    if (!batch || !batch.items.some((item) => item.job?.status === 'running')) return
    const timer = window.setTimeout(() => {
      fetch(`/batches/${batch.id}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((next: Batch | null) => { if (next) setBatch(next) })
        .catch(() => {})
    }, 300)
    return () => window.clearTimeout(timer)
  }, [batch])

  useEffect(() => {
    if (!confirming) return
    const dismiss = (event: Event) => {
      if (event.target instanceof Node && confirmRef.current?.contains(event.target)) return
      setConfirming(null)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setConfirming(null)
    }
    window.addEventListener('pointerdown', dismiss)
    window.addEventListener('click', dismiss)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('pointerdown', dismiss)
      window.removeEventListener('click', dismiss)
      window.removeEventListener('keydown', onKey)
    }
  }, [confirming])

  function patchRender(partial: Partial<RenderSettings>) {
    setRender((current) => ({ ...current, ...partial }))
  }

  function roomFor(count: number) {
    const room = MAX_BATCH - queue.length
    if (room <= 0 || count > room) toast.error('A batch can hold 20 images.')
    return Math.max(0, Math.min(room, count))
  }

  function addFiles(files: Iterable<File>) {
    const accepted: QueueItem[] = []
    for (const file of files) {
      if (!file.type.startsWith('image/')) {
        toast.error('That file is not an image.')
        continue
      }
      if (file.size > 20 * 1024 * 1024) {
        toast.error('That image is larger than 20 MB.')
        continue
      }
      accepted.push({
        id: crypto.randomUUID(),
        kind: 'file',
        file,
        name: file.name,
        preview: URL.createObjectURL(file),
      })
    }
    if (!accepted.length) return
    const keep = roomFor(accepted.length)
    accepted.slice(keep).forEach((item) => {
      if (item.kind === 'file') URL.revokeObjectURL(item.preview)
    })
    if (keep > 0) setQueue((current) => [...current, ...accepted.slice(0, keep)])
  }

  function addUrls(raw: string) {
    const lines = raw.split(/\s+/).map((line) => line.trim()).filter(Boolean)
    const accepted: QueueItem[] = []
    for (const line of lines) {
      try {
        const parsed = new URL(line)
        if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') throw new Error('bad')
        accepted.push({ id: crypto.randomUUID(), kind: 'url', url: parsed.toString() })
      } catch {
        toast.error('Give an http or https image URL.')
      }
    }
    if (!accepted.length) return
    const keep = roomFor(accepted.length)
    if (keep > 0) {
      setQueue((current) => [...current, ...accepted.slice(0, keep)])
      setUrlDraft('')
    }
  }

  function removeItem(id: string) {
    setQueue((current) => {
      const item = current.find((row) => row.id === id)
      if (item?.kind === 'file') URL.revokeObjectURL(item.preview)
      return current.filter((row) => row.id !== id)
    })
    setConfirming(null)
  }

  function takeDrop(transfer: DataTransfer) {
    setHot(false)
    if (batch || running) return
    if (transfer.files.length) {
      addFiles(transfer.files)
      return
    }
    const links = `${transfer.getData('text/uri-list')}\n${transfer.getData('text/plain')}`
      .split(/\s+/)
      .filter((line) => /^https?:\/\//i.test(line))
    if (links.length) addUrls([...new Set(links)].join(' '))
  }

  async function refresh(id: string) {
    const res = await fetch(`/batches/${id}`)
    const next = await readJson<Batch>(res)
    setBatch(next)
    return next
  }

  async function startBatch() {
    if (!key.keySaved) {
      toast.error('Add your OpenRouter key first.')
      return
    }
    if (!queue.length || submitting) return
    if (confirming !== 'batch') {
      sfx.arm()
      setConfirming('batch')
      return
    }
    setConfirming(null)
    sfx.pop()
    if (!await budgetAllows(chosen.usd * queue.length)) return
    setSubmitting(true)
    try {
      const created = await readJson<Batch>(await fetch('/batches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, render, urls: [] }),
      }))
      let current = created
      for (const item of queue) {
        if (item.kind === 'url') {
          current = await readJson<Batch>(await fetch(`/batches/${created.id}/url`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: item.url }),
          }))
        } else {
          current = await readJson<Batch>(await fetch(`/batches/${created.id}/file`, {
            method: 'POST',
            headers: { 'X-Sprite-Name': item.name },
            body: item.file,
          }))
        }
      }
      queue.forEach((item) => {
        if (item.kind === 'file') URL.revokeObjectURL(item.preview)
      })
      setQueue([])
      setBatch(current)
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Could not start the batch.')
    } finally {
      setSubmitting(false)
    }
  }

  async function redrawOne(job: Job) {
    if (confirming !== job.id) {
      sfx.arm()
      setConfirming(job.id)
      return
    }
    setConfirming(null)
    if (!batch) return
    if (!await budgetAllows(chosen.usd)) return
    try {
      await readJson<Job>(await fetch(`/jobs/${job.id}/redraw`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, render }),
      }))
      await refresh(batch.id)
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Could not redraw that sprite.')
    }
  }

  async function updateJobs(jobs: Job[]) {
    if (!batch || !jobs.length) return
    try {
      for (const job of jobs) {
        await readJson<Job>(await fetch(`/jobs/${job.id}/render`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ render }),
        }))
      }
      await refresh(batch.id)
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Could not update the sprite.')
    }
  }

  function takeDownload() {
    if (!batch) return
    setNag(false)
    const link = document.createElement('a')
    link.href = `/batches/${batch.id}/sprites.zip`
    link.download = 'sprites.zip'
    link.click()
  }

  function resetBatch() {
    setBatch(null)
    setConfirming(null)
    setNag(false)
  }

  const amounts = [0, successes, successes * 2, successes * 5]

  return (
    <div className="app">
      <Toasts />
      <StudioHeader builder="sprite" mode="batch">
        {batch && (
          <p className="status" role="status" aria-live="polite">
            {allSettled ? `${successes} of ${total} made` : `${settled} of ${total} through`}
          </p>
        )}
      </StudioHeader>
      <div className="workspace">
        <form ref={formRef} onSubmit={(event: FormEvent) => { event.preventDefault(); void startBatch() }}>
          <div className="rail-body">
            <div className="group">
              <ModelField models={modelOptions} value={model} onChange={(next) => { setConfirming(null); setModel(next) }} />
              <KeyField api={key} />
            </div>
            {!batch && (
              <div className="group">
                <div className="label-row spread">
                  <span className="kicker">Images</span>
                  <span className="count">{queue.length} / {MAX_BATCH}</span>
                </div>
                <button
                  type="button"
                  className={hot ? 'add hot' : 'add'}
                  onClick={() => fileRef.current?.click()}
                  onDragOver={(event) => { event.preventDefault(); setHot(true) }}
                  onDragLeave={() => setHot(false)}
                  onDrop={(event) => { event.preventDefault(); event.stopPropagation(); takeDrop(event.dataTransfer) }}
                >
                  <ImagePlus aria-hidden="true" />
                  Add images
                  <span>or drop a pile anywhere</span>
                </button>
                <input
                  ref={fileRef}
                  className="sr"
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={(event) => {
                    if (event.target.files) addFiles(event.target.files)
                    event.target.value = ''
                  }}
                />
                <div className="url-add">
                  <input
                    type="text"
                    placeholder="https:// or several URLs"
                    value={urlDraft}
                    spellCheck={false}
                    autoComplete="off"
                    aria-label="Image URLs"
                    onChange={(event) => setUrlDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key !== 'Enter') return
                      event.preventDefault()
                      addUrls(urlDraft)
                    }}
                  />
                  <button type="button" className="ghost" onClick={() => addUrls(urlDraft)} disabled={!urlDraft.trim()}>Add</button>
                </div>
                <ul className="queue">
                  <AnimatePresence initial={false}>
                    {queue.map((item) => (
                      <motion.li
                        key={item.id}
                        className="queue-row"
                        layout
                        initial={{ opacity: 0, x: -12, scale: 0.96 }}
                        animate={{ opacity: 1, x: 0, scale: 1 }}
                        exit={{ opacity: 0, x: 16, transition: { duration: 0.14 } }}
                        transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                      >
                        {item.kind === 'file'
                          ? <img src={item.preview} alt="" />
                          : <span className="queue-mark"><Link2 aria-hidden="true" /></span>}
                        <span className="queue-name">{item.kind === 'file' ? item.name : item.url}</span>
                        <button type="button" className="icon-btn small" aria-label="Remove" onClick={() => { sfx.tap(); removeItem(item.id) }}><X /></button>
                      </motion.li>
                    ))}
                  </AnimatePresence>
                </ul>
              </div>
            )}
            <SpriteFields render={render} idPrefix="batch-" onPatch={patchRender} />
          </div>
          <div className="dock">
            {finished.length > 0 && (
              <button type="button" className="ghost apply" disabled={running} onClick={() => void updateJobs(finished.flatMap((item) => item.job ? [item.job] : []))}>
                Update finished <span className="free">free</span>
              </button>
            )}
            {batch && !running
              ? <button type="button" className="ghost apply" onClick={resetBatch}>New batch</button>
              : (
                <button
                  ref={confirming === 'batch' ? confirmRef : undefined}
                  type="submit"
                  className={confirming === 'batch' ? 'make confirm' : 'make shine'}
                  disabled={running || !queue.length || !key.keySaved}
                >
                  {confirming === 'batch'
                    ? <>Tap again · {money(chosen.usd * billCount, chosen.estimate)}</>
                    : <><Sparkles aria-hidden="true" /> Make batch{queue.length > 0 && ` of ${queue.length}`} <Shortcut /></>}
                </button>
              )}
          </div>
        </form>
        <section className="stage batch-stage" aria-label="Batch" ref={stageRef}>
          {!batch && !queue.length && (
            <EmptyState title="The conga line is all line." art={<CongaScene />}>
              <p>Three blobs showed up. None of them brought a picture. Add images or paste a few URLs and they will each carry one.</p>
              <p>The confirm price is the model times how many you brought. Up to {MAX_BATCH} at a time.</p>
            </EmptyState>
          )}
          {!batch && queue.length > 0 && (
            <div className="queue-board">
              <p className="kicker">Up next</p>
              <ul className="cards">
                <AnimatePresence initial={false}>
                  {queue.map((item, index) => (
                    <motion.li
                      key={item.id}
                      className="card waiting"
                      layout
                      initial={{ opacity: 0, y: 18, scale: 0.9 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.8, transition: { duration: 0.14 } }}
                      transition={{ type: 'spring', stiffness: 380, damping: 28, delay: Math.min(index, 8) * 0.02 }}
                    >
                      <div className="thumb">
                        {item.kind === 'file' ? <img src={item.preview} alt="" /> : <Link2 aria-hidden="true" />}
                      </div>
                      <p className="queue-name">{item.kind === 'file' ? item.name : item.url}</p>
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            </div>
          )}
          {batch && (
            <>
              <div className="progress" aria-hidden="true">
                <motion.span
                  className={allSettled ? 'progress-fill done' : 'progress-fill'}
                  initial={false}
                  animate={{ width: `${total ? (settled / total) * 100 : 0}%` }}
                  transition={{ type: 'spring', stiffness: 120, damping: 22 }}
                />
              </div>
              <ul className="cards">
                {batch.items.map((item, index) => {
                  const job = item.job
                  const status = job?.status
                  const orb = status === 'running' ? ORB[job?.stage as keyof typeof ORB] ?? 'connecting' : null
                  return (
                    <motion.li
                      key={item.job_id}
                      className={`card ${status ?? 'waiting'}`}
                      initial={{ opacity: 0, y: 18, scale: 0.92 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ type: 'spring', stiffness: 360, damping: 28, delay: Math.min(index, 12) * 0.035 }}
                    >
                      <div className={status === 'done' ? 'thumb checker' : 'thumb'}>
                        {orb
                          ? <ThinkingOrb state={orb} size={64} theme="dark" aria-label={job?.stage || 'working'} />
                          : job?.files.final
                            ? <img key={job.files.final} className="pixel pop" src={job.files.final} alt="" />
                            : job?.files.reference
                              ? <img src={job.files.reference} alt="" />
                              : null}
                      </div>
                      <p className="queue-name" title={item.name}>{item.name}</p>
                      {status === 'error' && <p className="is-error">{job?.error || 'That image failed.'}</p>}
                      {status === 'running' && <p className="source-note">{STAGE_TEXT[job?.stage ?? ''] ?? job?.stage}</p>}
                      <div className="result-actions">
                        {status === 'error' && job && (
                          <button
                            type="button"
                            className={confirming === job.id ? 'make confirm' : 'ghost'}
                            ref={confirming === job.id ? confirmRef : undefined}
                            onClick={() => void redrawOne(job)}
                          >
                            {confirming === job.id ? `Tap again · ${oneLabel}` : 'Retry'}
                          </button>
                        )}
                        {status === 'done' && job && (
                          <>
                            <button type="button" className="ghost" disabled={running} onClick={() => void updateJobs([job])}>Update</button>
                            <button
                              type="button"
                              className={confirming === job.id ? 'make confirm' : 'ghost'}
                              ref={confirming === job.id ? confirmRef : undefined}
                              disabled={running && confirming !== job.id}
                              onClick={() => void redrawOne(job)}
                            >
                              {confirming === job.id ? `Tap again · ${oneLabel}` : 'Redraw'}
                            </button>
                          </>
                        )}
                      </div>
                    </motion.li>
                  )
                })}
              </ul>
            </>
          )}
          {successes > 0 && (
            <div className="downloads">
              <button type="button" className="make shine download" onClick={() => setNag(true)}>
                <Download aria-hidden="true" /> Download {successes === 1 ? 'the sprite' : `all ${successes}`}
              </button>
            </div>
          )}
        </section>
      </div>
      <DropVeil
        enabled={!batch && !running && !nag}
        title="Everybody in the pool."
        hint={`Images or links, up to ${MAX_BATCH}. Nothing is spent until Make batch.`}
        onDrop={takeDrop}
      />
      <PayModal open={nag} onClose={() => setNag(false)} amounts={amounts} onDownload={takeDownload} />
    </div>
  )
}
