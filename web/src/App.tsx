import { useCallback, useEffect, useRef, useState, type DragEvent, type FormEvent, type ReactNode } from 'react'
import { Check, Download, ImagePlus, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { ThinkingOrb, type OrbState } from 'thinking-orbs'
import { EmptyState } from './empty.tsx'
import { celebrate, sfx } from './fx.ts'
import { KeyField, useKey } from './key.tsx'
import { FrameScene } from './pixel.tsx'
import { ModelField, SpriteFields } from './sprite-controls.tsx'
import { StudioHeader } from './switch.tsx'
import { useOnDone, useSubmitShortcut } from './hooks.ts'
import { DEFAULT_RENDER, FALLBACK_MODEL, type IdleMeta, type Job, type RenderSettings, type StudioModel } from './types.ts'
import { DropVeil, PayModal, Sheet, Shortcut, Toasts } from './ui.tsx'

const ORB_STATE: Record<string, OrbState> = {
  queued: 'connecting',
  download: 'searching',
  redraw: 'weaving',
  pixelate: 'shaping',
  animate: 'breathing',
}

const STAGE_TEXT: Record<string, string> = {
  queued: 'Waiting to start.',
  download: 'Downloading the image.',
  upload: 'Reading the image.',
  redraw: 'Redrawing the creature. This is the slow step.',
  pixelate: 'Reducing it to a sprite.',
  animate: 'Building the idle.',
}

const PRICES = [0, 1, 2, 5] as const

const BACKDROPS = [
  { id: 'checker', label: 'Checker' },
  { id: 'night', label: 'Night' },
  { id: 'paper', label: 'Paper' },
  { id: 'grass', label: 'Grass' },
] as const

type Backdrop = (typeof BACKDROPS)[number]['id']

type SlotName = 'reference' | 'redraw' | 'sprite' | 'animation'

function workingSlot(stage: string): SlotName {
  if (stage === 'redraw') return 'redraw'
  if (stage === 'pixelate') return 'sprite'
  if (stage === 'animate') return 'animation'
  return 'reference'
}

function StageFigure({ title, step, backdrop, active, done, orb, children }: {
  title: string
  step: number
  backdrop?: Backdrop
  active: boolean
  done: boolean
  orb: OrbState | null
  children?: ReactNode
}) {
  const working = active && orb
  const classes = ['well', backdrop ? `bg-${backdrop}` : '', working ? 'working' : '', done && !working ? 'filled' : '']
  return (
    <figure className={working ? 'is-working' : done ? 'is-done' : ''}>
      <div className={classes.filter(Boolean).join(' ')}>
        {working
          ? <ThinkingOrb state={orb} size={64} theme="dark" aria-label={title} />
          : children}
      </div>
      <figcaption>
        <span className="step">{done && !working ? <Check aria-hidden="true" /> : step}</span>
        {title}
      </figcaption>
    </figure>
  )
}

type Notice =
  | { kind: 'clear' }
  | { kind: 'work'; text: string; state: OrbState }

type Staged =
  | { kind: 'file'; file: File; preview: string }
  | { kind: 'url'; url: string }

function sourceLabel(value: string) {
  try {
    const parsed = new URL(value)
    const last = parsed.pathname.split('/').filter(Boolean).pop()
    return decodeURIComponent(last || parsed.hostname)
  } catch {
    return value
  }
}

async function readJob(res: Response): Promise<Job> {
  const body = await res.json().catch(() => ({})) as Partial<Job> & { error?: string }
  if (!res.ok) throw new Error(body.error || 'Could not reach the studio.')
  return body as Job
}

function IdlePreview({ sheetUrl, metaUrl }: { sheetUrl: string; metaUrl: string }) {
  const [meta, setMeta] = useState<IdleMeta | null>(null)
  const [frame, setFrame] = useState(0)

  useEffect(() => {
    let gone = false
    fetch(metaUrl)
      .then((res) => (res.ok ? res.json() : null))
      .then((data: IdleMeta | null) => {
        if (!gone && data?.frame_ms?.length) setMeta(data)
      })
      .catch(() => {})
    return () => { gone = true }
  }, [metaUrl])

  useEffect(() => {
    if (!meta) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) return
    const total = meta.frame_ms.reduce((sum, ms) => sum + ms, 0)
    if (total <= 0) return
    const tick = () => {
      let remaining = performance.now() % total
      let index = 0
      while (index < meta.frame_ms.length - 1 && remaining >= meta.frame_ms[index]) {
        remaining -= meta.frame_ms[index]
        index += 1
      }
      setFrame(index)
    }
    tick()
    const timer = window.setInterval(tick, 40)
    return () => window.clearInterval(timer)
  }, [meta])

  if (!meta) return null
  const count = meta.frame_ms.length
  const pos = count > 1 ? (frame / (count - 1)) * 100 : 0
  return (
    <div
      className="pixel idle"
      role="img"
      aria-label="Idle animation"
      style={{
        backgroundImage: `url("${sheetUrl}")`,
        backgroundSize: `${count * 100}% 100%`,
        backgroundPosition: `${pos}% 0`,
      }}
    />
  )
}

export default function App() {
  const [models, setModels] = useState<StudioModel[]>([])
  const [model, setModel] = useState(FALLBACK_MODEL.id)
  const [render, setRender] = useState<RenderSettings>(DEFAULT_RENDER)
  const [job, setJob] = useState<Job | null>(null)
  const [looked, setLooked] = useState(false)
  const [notice, setNotice] = useState<Notice>({ kind: 'clear' })
  const [sheet, setSheet] = useState(false)
  const [sheetUrl, setSheetUrl] = useState('')
  const [sheetError, setSheetError] = useState('')
  const [sheetHot, setSheetHot] = useState(false)
  const [addHot, setAddHot] = useState(false)
  const [staged, setStaged] = useState<Staged | null>(null)
  const [dismissedId, setDismissedId] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [nag, setNag] = useState(false)
  const [backdrop, setBackdrop] = useState<Backdrop>('checker')
  const key = useKey()
  const toastedError = useRef('')
  const [rerastering, setRerastering] = useState(false)
  const [holdAnimation, setHoldAnimation] = useState(false)
  const spriteShownAt = useRef<number | null>(null)
  const holdTimer = useRef<number | null>(null)
  const tookOver = useRef(false)
  const modelTouched = useRef(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const stagedRef = useRef<Staged | null>(null)
  const makeRef = useRef<HTMLButtonElement>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const spriteRef = useRef<HTMLDivElement>(null)
  useSubmitShortcut(formRef)

  useEffect(() => {
    document.title = 'KALDR STUDIO'
    let gone = false
    fetch('/models')
      .then((res) => (res.ok ? res.json() : null))
      .then((body: { models?: StudioModel[] } | null) => {
        if (gone || !body?.models?.length) return
        setModels(body.models)
      })
      .catch(() => {})
    fetch('/jobs/latest')
      .then((res) => (res.ok ? res.json() : null))
      .then((latest: Job | null) => {
        if (gone || tookOver.current || !latest) return
        setJob(latest)
        if (latest.model && !modelTouched.current) setModel(latest.model)
      })
      .catch(() => {})
      .finally(() => { if (!gone) setLooked(true) })
    return () => { gone = true }
  }, [])

  useEffect(() => {
    if (!confirming) return
    const dismiss = (event: Event) => {
      if (event.target instanceof Node && makeRef.current?.contains(event.target)) return
      setConfirming(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setConfirming(false)
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

  const takeDownload = useCallback(() => {
    if (!job) return
    setNag(false)
    const link = document.createElement('a')
    link.href = `/jobs/${job.id}/sprite.zip`
    link.download = 'sprite.zip'
    document.body.appendChild(link)
    link.click()
    link.remove()
  }, [job])

  useEffect(() => {
    stagedRef.current = staged
  }, [staged])

  useEffect(() => () => {
    const current = stagedRef.current
    if (current?.kind === 'file') URL.revokeObjectURL(current.preview)
  }, [])

  useEffect(() => {
    const preventNavigation = (event: globalThis.DragEvent) => {
      const types = [...(event.dataTransfer?.types ?? [])]
      if (!types.includes('Files') && !types.includes('text/uri-list')) return
      event.preventDefault()
    }
    window.addEventListener('dragover', preventNavigation)
    window.addEventListener('drop', preventNavigation)
    return () => {
      window.removeEventListener('dragover', preventNavigation)
      window.removeEventListener('drop', preventNavigation)
    }
  }, [])

  useEffect(() => {
    if (!job || job.status !== 'running') return
    const timer = window.setTimeout(() => {
      fetch(`/jobs/${job.id}`)
        .then((res) => readJob(res))
        .then((next) => {
          setJob(next)
          if (next.status === 'error') {
            resetAnimationHold()
            setRerastering(false)
            setNotice({ kind: 'clear' })
            return
          }
          armAnimationHold(next)
          if (next.status !== 'running') {
            setRerastering(false)
            setNotice({ kind: 'clear' })
          }
        })
        .catch((error: unknown) => {
          toast.error(error instanceof Error ? error.message : 'That job disappeared.')
        })
    }, 300)
    return () => window.clearTimeout(timer)
  }, [job])

  useEffect(() => {
    if (job?.status !== 'error') return
    const text = job.error || 'Something went wrong.'
    const mark = `${job.id}:${text}`
    if (toastedError.current === mark) return
    toastedError.current = mark
    sfx.error()
    toast.error(text)
  }, [job])

  // Only jobs started on this visit get a party. Reloading a finished one is not news.
  useOnDone(job?.status === 'done' && Boolean(job.files.final), () => {
    if (tookOver.current) celebrate(spriteRef.current)
  })

  const running = notice.kind === 'work' || job?.status === 'running' || holdAnimation
  const orbState: OrbState | null = notice.kind === 'work'
    ? notice.state
    : job?.status === 'running'
      ? (ORB_STATE[job.stage] ?? 'working')
      : null
  const statusText = job?.status === 'running'
    ? (STAGE_TEXT[job.stage] ?? 'Working.')
    : notice.kind === 'work'
      ? notice.text
      : holdAnimation
        ? 'Building the idle.'
        : ''
  const showActivity = Boolean(statusText || orbState)
  const sprite = (job?.render?.canvas || 48) * 5
  const canUpdate = Boolean(job?.files.stylized) && !running
  const modelOptions = models.length ? models : [{ ...FALLBACK_MODEL, id: model }]
  const modelPrice = modelOptions.find((item) => item.id === model)?.price ?? modelOptions[0].price

  function patchRender(patch: Partial<RenderSettings>) {
    setRender((current) => ({ ...current, ...patch }))
  }

  const keptReference = job?.files.reference && job.id !== dismissedId ? job.files.reference : ''
  const sourceImage = staged?.kind === 'file' ? staged.preview : keptReference
  const hasSource = Boolean(staged) || Boolean(keptReference)
  const activeSlot: SlotName | null = !running || rerastering
    ? null
    : job?.status === 'running'
      ? workingSlot(job.stage)
      : 'reference'
  function slotActive(name: SlotName) {
    if (name === 'animation' && holdAnimation) return true
    if (rerastering) {
      const spriteStillWorking = job?.status === 'running' && job.stage !== 'animate'
      if (name === 'sprite') return spriteStillWorking
      if (name === 'animation') return true
      return false
    }
    return activeSlot === name
  }
  function slotOrb(name: SlotName): OrbState | null {
    if (!slotActive(name)) return null
    if (name === 'animation' && (rerastering || holdAnimation)) return 'breathing'
    if (rerastering && name === 'sprite') return 'shaping'
    return orbState
  }
  const referenceSrc = slotActive('reference')
    ? ''
    : (job?.files.reference || (staged?.kind === 'file' ? staged.preview : ''))

  function closeSheet() {
    setSheet(false)
    setSheetHot(false)
    setSheetError('')
  }

  function openSheet() {
    if (running) return
    setSheetUrl('')
    setSheetError('')
    setSheetHot(false)
    setSheet(true)
  }

  function releaseStaged(current: Staged | null) {
    if (current?.kind === 'file') URL.revokeObjectURL(current.preview)
  }

  function clearStaged() {
    releaseStaged(staged)
    setConfirming(false)
    setStaged(null)
  }

  function commitStaged(next: Staged) {
    if (staged !== next) releaseStaged(staged)
    setConfirming(false)
    setStaged(next)
    setNotice({ kind: 'clear' })
    closeSheet()
  }

  function reportIntake(message: string) {
    if (sheet) setSheetError(message)
    else toast.error(message)
  }

  function stageFile(file: File) {
    const image = file.type.startsWith('image/') || /\.(png|jpe?g|webp|gif)$/i.test(file.name)
    if (!image) {
      reportIntake('Use a PNG, JPEG, WebP, or GIF.')
      return
    }
    if (file.size > 20 * 1024 * 1024) {
      reportIntake('That image is larger than 20 MB.')
      return
    }
    commitStaged({ kind: 'file', file, preview: URL.createObjectURL(file) })
  }

  function stageUrl(raw: string) {
    const nextUrl = raw.trim()
    let parsed: URL
    try {
      parsed = new URL(nextUrl)
    } catch {
      reportIntake('Paste an http or https image URL.')
      return
    }
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      reportIntake('Paste an http or https image URL.')
      return
    }
    commitStaged({ kind: 'url', url: nextUrl })
  }

  function resetAnimationHold() {
    spriteShownAt.current = null
    if (holdTimer.current) window.clearTimeout(holdTimer.current)
    holdTimer.current = null
    setHoldAnimation(false)
  }

  function armAnimationHold(next: Job) {
    const spriteDone = Boolean(next.files.final) && (
      next.status === 'done' || (next.status === 'running' && next.stage === 'animate')
    )
    if (!spriteDone || spriteShownAt.current != null) return
    spriteShownAt.current = performance.now()
    setHoldAnimation(true)
    holdTimer.current = window.setTimeout(() => {
      holdTimer.current = null
      setHoldAnimation(false)
    }, 1000)
  }

  function beginWork(text: string, state: OrbState) {
    tookOver.current = true
    closeSheet()
    resetAnimationHold()
    setJob(null)
    setNotice({ kind: 'work', text, state })
  }

  async function acceptJob(res: Response) {
    const next = await readJob(res)
    setJob(next)
    armAnimationHold(next)
    setNotice({ kind: 'clear' })
  }

  function failStart(error: unknown, fallback: string) {
    toast.error(error instanceof Error ? error.message : fallback)
  }

  async function startFromUrl(nextUrl: string) {
    beginWork('Starting.', 'connecting')
    try {
      const res = await fetch('/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: nextUrl, render, model }),
      })
      await acceptJob(res)
      clearStaged()
    } catch (error: unknown) {
      failStart(error, 'Could not start.')
    }
  }

  async function startFromFile(file: File) {
    beginWork('Reading the image.', 'searching')
    try {
      const res = await fetch('/jobs/file', {
        method: 'POST',
        headers: {
          'Content-Type': file.type || 'application/octet-stream',
          'X-Sprite-Model': model,
          'X-Sprite-Render': JSON.stringify(render),
          'X-Sprite-Name': encodeURIComponent(file.name),
        },
        body: file,
      })
      await acceptJob(res)
      clearStaged()
    } catch (error: unknown) {
      failStart(error, 'Could not read that image.')
    }
  }

  function droppedUrl(transfer: DataTransfer) {
    const text = `${transfer.getData('text/uri-list')}\n${transfer.getData('text/plain')}`
    return text.split(/[\s\n]/).map((item) => item.trim()).find((item) => /^https?:\/\//i.test(item)) || ''
  }

  function droppedFile(transfer: DataTransfer) {
    return [...transfer.files].find((file) => file.type.startsWith('image/') || /\.(png|jpe?g|webp|gif)$/i.test(file.name))
  }

  function dragCarriesImage(transfer: DataTransfer) {
    const types = [...transfer.types]
    return types.includes('Files') || types.includes('text/uri-list') || types.includes('text/plain')
  }

  function onDragOver(event: DragEvent) {
    if (!dragCarriesImage(event.dataTransfer)) return
    event.preventDefault()
    event.stopPropagation()
    event.dataTransfer.dropEffect = 'copy'
    setSheetHot(true)
  }

  function takeDrop(transfer: DataTransfer) {
    const file = droppedFile(transfer)
    if (file) {
      stageFile(file)
      return
    }
    if (transfer.files.length) {
      reportIntake('Use a PNG, JPEG, WebP, or GIF.')
      return
    }
    const link = droppedUrl(transfer)
    if (!link) {
      reportIntake('Drop an image or a link.')
      return
    }
    stageUrl(link)
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    event.stopPropagation()
    setSheetHot(false)
    takeDrop(event.dataTransfer)
  }

  function onAddDragOver(event: DragEvent<HTMLButtonElement>) {
    if (running || !dragCarriesImage(event.dataTransfer)) return
    event.preventDefault()
    event.stopPropagation()
    event.dataTransfer.dropEffect = 'copy'
    setAddHot(true)
  }

  function onAddDragLeave(event: DragEvent<HTMLButtonElement>) {
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
    setAddHot(false)
  }

  function onAddDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault()
    event.stopPropagation()
    setAddHot(false)
    if (running) return
    takeDrop(event.dataTransfer)
  }

  async function remakeKept(current: Job) {
    if (/^https?:\/\//i.test(current.url)) {
      await startFromUrl(current.url)
      return
    }
    if (!current.files.reference) return
    const res = await fetch(current.files.reference)
    if (!res.ok) throw new Error('Could not read that image.')
    const blob = await res.blob()
    const file = new File([blob], sourceLabel(current.url) || 'reference.png', { type: blob.type || 'image/png' })
    await startFromFile(file)
  }

  function makeSprite(event: FormEvent) {
    event.preventDefault()
    if (running || !hasSource) return
    if (!key.keySaved) {
      toast.error('Add your OpenRouter key first.')
      return
    }
    if (!confirming) {
      sfx.arm()
      setConfirming(true)
      return
    }
    setConfirming(false)
    sfx.pop()
    if (staged?.kind === 'file') {
      void startFromFile(staged.file)
      return
    }
    if (staged?.kind === 'url') {
      void startFromUrl(staged.url)
      return
    }
    if (job) {
      void remakeKept(job).catch((error: unknown) => {
        toast.error(error instanceof Error ? error.message : 'Could not start.')
      })
    }
  }

  async function updateSprite() {
    if (!job) return
    tookOver.current = true
    resetAnimationHold()
    setRerastering(true)
    setNotice({ kind: 'work', text: 'Updating the sprite.', state: 'shaping' })
    try {
      const res = await fetch(`/jobs/${job.id}/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ render }),
      })
      const next = await readJob(res)
      setJob(next)
      if (next.status === 'error') {
        resetAnimationHold()
        setRerastering(false)
        setNotice({ kind: 'clear' })
        return
      }
      armAnimationHold(next)
      if (next.status !== 'running') {
        setRerastering(false)
        setNotice({ kind: 'clear' })
      }
    } catch (error: unknown) {
      resetAnimationHold()
      setRerastering(false)
      toast.error(error instanceof Error ? error.message : 'Could not update the sprite.')
    }
  }

  const showEmpty = looked && !job && notice.kind === 'clear' && !hasSource
  const finished = job?.status === 'done' && Boolean(job.files.final || job.files.idle || job.files.idle_json || job.files.gif)

  return (
    <div className="app" style={{ ['--sprite' as string]: `${sprite}px` }}>
      <Toasts />
      <StudioHeader builder="sprite" mode="one">
        {showActivity && (
          <p className="status" role="status" aria-live="polite">{statusText}</p>
        )}
      </StudioHeader>
      <div className="workspace">
        <form ref={formRef} onSubmit={makeSprite}>
          <div className="rail-body">
          <div className="group">
            <ModelField
              models={modelOptions}
              value={model}
              onChange={(next) => {
                modelTouched.current = true
                setConfirming(false)
                setModel(next)
              }}
            />
            <KeyField api={key} />
            <div className="source">
              <span className="kicker" id="image-label">Image</span>
              {sourceImage && <img key={sourceImage} className="source-preview reveal" src={sourceImage} alt="" />}
              {staged?.kind === 'url' && <p className="source-note">{sourceLabel(staged.url)}</p>}
              {!sourceImage && staged?.kind !== 'url' && (
                <button
                  type="button"
                  className={addHot ? 'add hot' : 'add'}
                  disabled={running}
                  onClick={openSheet}
                  onDragOver={onAddDragOver}
                  onDragLeave={onAddDragLeave}
                  onDrop={onAddDrop}
                >
                  <ImagePlus aria-hidden="true" />
                  Add image
                  <span>or drop one anywhere</span>
                </button>
              )}
              {(sourceImage || staged) && (
                <div className="source-links">
                  <button type="button" disabled={running} onClick={openSheet}>Change image</button>
                  <button
                    type="button"
                    disabled={running}
                    onClick={() => {
                      setConfirming(false)
                      if (staged) clearStaged()
                      else if (job) setDismissedId(job.id)
                    }}
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>
          </div>
          <SpriteFields render={render} onPatch={patchRender} />
          </div>
          <div className="dock">
            {canUpdate && (
              <button
                type="button"
                className="ghost apply"
                onClick={updateSprite}
                title="Re-renders the sprite you already have. Does not call the model."
              >
                Update sprite <span className="free">free</span>
              </button>
            )}
            <button
              ref={makeRef}
              type="submit"
              className={confirming ? 'make confirm' : 'make shine'}
              disabled={running || !hasSource || !key.keySaved}
            >
              {confirming
                ? <>Tap again · {modelPrice}</>
                : <><Sparkles aria-hidden="true" /> Make sprite <Shortcut /></>}
            </button>
          </div>
        </form>
        <section className="stage" aria-label="Previews">
          {showEmpty && (
            <EmptyState title="The frame is hungry." art={<FrameScene />}>
              <p>It eats PNGs. JPEGs too. It is not picky. Add an image on the left, or just drop one anywhere on the page.</p>
              <p>Then Make sprite. The button asks twice. The second tap is the one that spends the money.</p>
            </EmptyState>
          )}
          {!showEmpty && (
            <>
              <div className="pair">
                <StageFigure title="Reference" step={1} active={slotActive('reference')} done={Boolean(referenceSrc)} orb={slotOrb('reference')}>
                  {referenceSrc && <img key={referenceSrc} className="photo reveal" src={referenceSrc} alt="Reference image" />}
                </StageFigure>
                <StageFigure title="Redraw" step={2} active={slotActive('redraw')} done={Boolean(job?.files.stylized)} orb={slotOrb('redraw')}>
                  {job?.files.stylized && !slotActive('redraw') && <img key={job.files.stylized} className="photo reveal" src={job.files.stylized} alt="Stylized redraw" />}
                </StageFigure>
              </div>
              <div className="pair results" ref={spriteRef}>
                <StageFigure title="Sprite" step={3} backdrop={backdrop} active={slotActive('sprite')} done={Boolean(job?.files.final)} orb={slotOrb('sprite')}>
                  {job?.files.final && !slotActive('sprite') && (
                    <img key={job.files.final} className="pixel pop" width={sprite} height={sprite} src={job.files.final} alt={`${job.render?.canvas ?? 48} by ${job.render?.canvas ?? 48} sprite`} />
                  )}
                </StageFigure>
                <StageFigure title="Animation" step={4} backdrop={backdrop} active={slotActive('animation')} done={Boolean(job?.files.idle)} orb={slotOrb('animation')}>
                  {job?.files.idle && job.files.idle_json && !slotActive('animation') && (
                    <IdlePreview key={job.files.idle} sheetUrl={job.files.idle} metaUrl={job.files.idle_json} />
                  )}
                </StageFigure>
              </div>
              <div className="stage-foot">
                <div className="swatches" role="group" aria-label="Sprite backdrop">
                  {BACKDROPS.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`swatch bg-${item.id}`}
                      aria-pressed={backdrop === item.id}
                      title={item.label}
                      aria-label={`${item.label} backdrop`}
                      onClick={() => {
                        sfx.tap()
                        setBackdrop(item.id)
                      }}
                    />
                  ))}
                </div>
                {finished && (
                  <button type="button" className="make shine download" onClick={() => setNag(true)}>
                    <Download aria-hidden="true" /> Download package
                  </button>
                )}
              </div>
            </>
          )}
        </section>
      </div>
      <DropVeil
        enabled={!running && !sheet && !nag}
        title="Drop it in the frame."
        hint="An image, or a link to one. Nothing is spent until Make sprite."
        onDrop={takeDrop}
      />
      <Sheet
        open={sheet}
        onClose={closeSheet}
        labelledBy="intake-title"
        drop={{
          onDragOver,
          onDragLeave: (event) => {
            if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
            setSheetHot(false)
          },
          onDrop,
        }}
      >
        <h2 id="intake-title">Add an image</h2>
        <p>Choose a file, drop one, or paste a URL.</p>
        <div className={sheetHot ? 'dropwell hot' : 'dropwell'}>
          <button type="button" className="make" onClick={() => fileRef.current?.click()}>Choose a file</button>
          <p>or drop it here</p>
          <input
            ref={fileRef}
            className="sr"
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif,.png,.jpg,.jpeg,.webp,.gif"
            onChange={(event) => {
              const file = event.target.files?.[0]
              event.target.value = ''
              if (file) stageFile(file)
            }}
          />
        </div>
        <label htmlFor="sheet-url">Image URL</label>
        <input
          id="sheet-url"
          type="text"
          placeholder="https://"
          autoComplete="off"
          spellCheck={false}
          value={sheetUrl}
          onChange={(event) => setSheetUrl(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter') return
            event.preventDefault()
            stageUrl(sheetUrl)
          }}
        />
        {sheetError && <p className="is-error shake" key={sheetError}>{sheetError}</p>}
        <div className="source-row">
          <button type="button" className="ghost" onClick={() => stageUrl(sheetUrl)}>Use URL</button>
          <button type="button" className="ghost" onClick={closeSheet}>Cancel</button>
        </div>
      </Sheet>
      <PayModal open={nag} onClose={() => setNag(false)} amounts={PRICES} onDownload={takeDownload} />
    </div>
  )
}
