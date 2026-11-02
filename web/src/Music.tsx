import { useEffect, useLayoutEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Dices, Download, FileAudio, Link2, ListMusic, Megaphone, Music, X } from 'lucide-react'
import { toast } from 'sonner'
import { ThinkingOrb, type OrbState } from 'thinking-orbs'
import { EmptyState } from './empty.tsx'
import { celebrate, sfx } from './fx.ts'
import { BubbleScene, NapScene, ShelfScene, TapeScene } from './pixel.tsx'
import { StudioHeader, type BuilderMode } from './switch.tsx'
import { useSubmitShortcut } from './hooks.ts'
import { TrackList, type LoopTrack, type Strips } from './Mixer.tsx'
import { useSavedSettings } from './settings.ts'
import { DropVeil, RangeField, Segment, Sheet, Shortcut, Toasts, Toggle } from './ui.tsx'

const MAX_BATCH = 8
const MAX_BYTES = 80 * 1024 * 1024
const MEDIA = /\.(mp3|mp4|m4a|wav|ogg|webm|flac|mov|mkv|aac|m4v)$/i

const STAGE_TEXT: Record<string, string> = {
  queued: 'Waiting for the studio to finish what it is already doing.',
  download: 'Downloading the recording.',
  separate: 'Pulling the song apart. The voice stays out.',
  transcribe: 'Writing the notes.',
  render: 'Making the loop.',
}

const STAGE_ORB: Record<string, OrbState> = {
  queued: 'connecting',
  download: 'searching',
  separate: 'weaving',
  transcribe: 'shaping',
  render: 'breathing',
}

type Lead = 'vocal-melody' | 'instrument' | 'none'

type SpeakSettings = {
  text: string
  pitch: number
  speed: number
  variation: number
  length: number
  drop: number
  pauses: number
  brightness: number
  lift: number
  tone: number
  seed: string
}

type ScoreSettings = {
  takes: number
  style: 'soft' | 'gb'
  classic: boolean
  lead: Lead
  min_seconds: number
  max_seconds: number
  start_after: number
  space: number
  brightness: number
  lead_level: number
  chords_level: number
  bass_level: number
  drums_level: number
}

const LEAD_OPTIONS: { value: Lead; label: string }[] = [
  { value: 'vocal-melody', label: 'Sung notes, no voice' },
  { value: 'instrument', label: 'Instruments only' },
  { value: 'none', label: 'No lead' },
]

type ScoreInfo = {
  bpm: number
  key: string | null
  loop_start: number
  loop_end: number
  seconds: number
}

type TakeFiles = { wav: string | null; ogg: string | null; midi?: string | null; zip: string | null; tracks?: LoopTrack[] }

type ScoreTake = { number: number; info: ScoreInfo; files: TakeFiles }

type ScoreJob = {
  id: string
  name: string
  status: 'running' | 'done' | 'error'
  stage: string
  error: string | null
  info: ScoreInfo | null
  files: TakeFiles
  takes?: ScoreTake[]
}

type Source =
  | { kind: 'file'; file: File; name: string }
  | { kind: 'url'; url: string }

type BatchItem = {
  key: string
  name: string
  source: Source
  job: ScoreJob | null
}

const SPEAK_DEFAULT: SpeakSettings = {
  text: '', pitch: 300, speed: 16, variation: 3, length: 1, drop: 1, pauses: 1, brightness: 6000, lift: 1, tone: 0.5, seed: '',
}

type Voice = Omit<SpeakSettings, 'text' | 'seed'>

const VOICES: { id: string; label: string; voice: Voice }[] = [
  { id: 'chipper', label: 'Chipper', voice: { pitch: 300, speed: 16, variation: 3, length: 1, drop: 1, pauses: 1, brightness: 6000, lift: 1, tone: 0.5 } },
  { id: 'tiny', label: 'Tiny', voice: { pitch: 440, speed: 24, variation: 5, length: 0.7, drop: 1.4, pauses: 0.8, brightness: 8500, lift: 1.6, tone: 0.35 } },
  { id: 'grump', label: 'Grump', voice: { pitch: 170, speed: 10, variation: 1, length: 1.4, drop: 2.2, pauses: 1.4, brightness: 2600, lift: 0.4, tone: 0.7 } },
  { id: 'robot', label: 'Robot', voice: { pitch: 260, speed: 18, variation: 0, length: 1, drop: 0, pauses: 1, brightness: 5000, lift: 0, tone: 0.5 } },
  { id: 'shopkeep', label: 'Shopkeep', voice: { pitch: 330, speed: 14, variation: 4, length: 1.1, drop: 1, pauses: 1.6, brightness: 6500, lift: 1.4, tone: 0.45 } },
]

const LINES = [
  'Hey there. Want to buy something?',
  'You again! I was just about to close.',
  'That one bites. Lovingly. Mostly.',
  'Have you tried turning the moon off and on again?',
  'I found a pearl in my soup. Is that good?',
  'Ahem. AHEM. Thank you.',
]

type SavedSpeech = Voice & { seed: number | null }

function speakWithoutLine({ pitch, speed, variation, length, drop, pauses, brightness, lift, tone }: SpeakSettings): Voice {
  return { pitch, speed, variation, length, drop, pauses, brightness, lift, tone }
}

function voiceOf(settings: SpeakSettings): string | null {
  return VOICES.find(({ voice }) => (Object.keys(voice) as (keyof Voice)[]).every((name) => voice[name] === settings[name]))?.id ?? null
}
const SCORE_DEFAULT: ScoreSettings = {
  takes: 3,
  style: 'soft',
  classic: false,
  lead: 'vocal-melody',
  min_seconds: 40,
  max_seconds: 90,
  start_after: 0,
  space: 1,
  brightness: 1,
  lead_level: 1,
  chords_level: 1,
  bass_level: 1,
  drums_level: 1,
}

async function readJson<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => ({})) as T & { error?: string }
  if (!res.ok) throw new Error(body.error || 'Could not reach the studio.')
  return body
}

function stageText(stage: string) {
  return STAGE_TEXT[stage] || 'Working on the loop.'
}

function scoreLine(info: ScoreInfo) {
  const bits = [`${info.bpm} BPM`]
  if (info.key) bits.push(info.key)
  bits.push(`${info.seconds}s loop`)
  bits.push(`${info.loop_start}s–${info.loop_end}s of the original`)
  return bits.join(' · ')
}

function mediaFile(file: File) {
  return file.type.startsWith('audio/') || file.type.startsWith('video/') || MEDIA.test(file.name)
}

function droppedUrl(transfer: DataTransfer) {
  const text = `${transfer.getData('text/uri-list')}\n${transfer.getData('text/plain')}`
  return text.split(/[\s\n]/).map((item) => item.trim()).find((item) => /^https?:\/\//i.test(item)) || ''
}

function sourceLabel(value: string) {
  try {
    const parsed = new URL(value)
    const last = parsed.pathname.split('/').filter(Boolean).pop()
    return decodeURIComponent(last || parsed.hostname)
  } catch {
    return value
  }
}

export default function MusicApp({ mode }: { mode: BuilderMode | 'speech' }) {
  const batch = mode === 'batch'
  const speech = mode === 'speech'
  const [speak, setSpeak] = useState<SpeakSettings>(SPEAK_DEFAULT)
  const [settings, setSettings] = useState<ScoreSettings>(SCORE_DEFAULT)
  const [source, setSource] = useState<Source | null>(null)
  const [urlDraft, setUrlDraft] = useState('')
  const [items, setItems] = useState<BatchItem[]>([])
  const [started, setStarted] = useState(false)
  const [job, setJob] = useState<ScoreJob | null>(null)
  const [clip, setClip] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [hot, setHot] = useState(false)
  const [sheet, setSheet] = useState(false)
  const [sheetUrl, setSheetUrl] = useState('')
  const [sheetHot, setSheetHot] = useState(false)
  const [sheetError, setSheetError] = useState('')
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const [talking, setTalking] = useState(false)
  const [rightsFor, setRightsFor] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const stageRef = useRef<HTMLElement>(null)
  const alive = useRef(true)
  const clipRef = useRef<string | null>(null)
  useSubmitShortcut(formRef)
  useSavedSettings<ScoreSettings>('loop', settings, setSettings)
  useSavedSettings<SavedSpeech>(
    'speech',
    { ...speakWithoutLine(speak), seed: /^\d+$/.test(speak.seed.trim()) ? Number(speak.seed) : null },
    (saved) => setSpeak((current) => ({ ...current, ...saved, seed: saved.seed === null ? '' : String(saved.seed) })),
  )
  // Every new recording needs its own rights confirmation.
  const recordings = batch ? items.map((item) => item.key).join('|') : source?.kind === 'url' ? source.url : source ? `${source.file.name}:${source.file.size}` : ''
  const rights = recordings !== '' && rightsFor === recordings
  useEffect(() => {
    document.title = 'KALDR STUDIO'
    alive.current = true
    return () => { alive.current = false }
  }, [])

  useEffect(() => {
    if (speech || batch) return
    let gone = false
    void fetch('/audio/score/latest')
      .then((res) => (res.ok ? res.json() : null))
      .then((body: ScoreJob | null) => {
        if (gone || !body?.files?.wav) return
        setJob((current) => current ?? body)
      })
      .catch(() => {})
    return () => { gone = true }
  }, [batch, speech])

  useEffect(() => {
    clipRef.current = clip
  }, [clip])

  useEffect(() => () => {
    if (clipRef.current) URL.revokeObjectURL(clipRef.current)
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

  function patchSpeak(patch: Partial<SpeakSettings>) {
    setSpeak((current) => ({ ...current, ...patch }))
  }

  function patchScore(patch: Partial<ScoreSettings>) {
    setSettings((current) => {
      const next = { ...current, ...patch }
      if (next.min_seconds > next.max_seconds) {
        if ('min_seconds' in patch) next.max_seconds = next.min_seconds
        else next.min_seconds = next.max_seconds
      }
      return next
    })
  }

  function closeSheet() {
    setSheet(false)
    setSheetHot(false)
    setSheetError('')
  }

  function openSheet() {
    if (busy) return
    setSheetUrl('')
    setSheetError('')
    setSheetHot(false)
    setSheet(true)
  }

  function reportIntake(message: string) {
    if (sheet) setSheetError(message)
    else toast.error(message)
  }

  function takeFiles(files: File[]) {
    const accepted = files.filter(mediaFile)
    if (!accepted.length) {
      reportIntake('Use an audio or video file. mp4, mp3, wav, and the usual sorts.')
      return
    }
    const oversized = accepted.find((file) => file.size > MAX_BYTES)
    if (oversized) {
      reportIntake('That file is larger than 80 MB.')
      return
    }
    if (batch) {
      setItems((current) => {
        const room = MAX_BATCH - current.length
        if (room <= 0) {
          toast.error('A batch can hold 8 recordings.')
          return current
        }
        const next = accepted.slice(0, room).map((file) => ({
          key: crypto.randomUUID(),
          name: file.name,
          source: { kind: 'file' as const, file, name: file.name },
          job: null,
        }))
        if (accepted.length > room) toast.error('A batch can hold 8 recordings.')
        return [...current, ...next]
      })
      return
    }
    const file = accepted[0]
    setSource({ kind: 'file', file, name: file.name })
    setJob(null)
    closeSheet()
  }

  function addUrl(raw = urlDraft) {
    const url = raw.trim()
    if (!/^https?:\/\//i.test(url)) {
      reportIntake('Give an http or https address.')
      return
    }
    if (batch) {
      setItems((current) => {
        if (current.length >= MAX_BATCH) {
          toast.error('A batch can hold 8 recordings.')
          return current
        }
        const name = decodeURIComponent(url.split('/').pop() || url)
        return [...current, { key: crypto.randomUUID(), name, source: { kind: 'url', url }, job: null }]
      })
      setUrlDraft('')
      return
    }
    setSource({ kind: 'url', url })
    setUrlDraft('')
    setJob(null)
    closeSheet()
  }

  function takeDrop(transfer: DataTransfer) {
    setHot(false)
    setSheetHot(false)
    if (busy) return
    const files = [...transfer.files]
    if (files.length) {
      takeFiles(files)
      return
    }
    const link = droppedUrl(transfer)
    if (!link) {
      reportIntake('Drop an audio or video file, or a link.')
      return
    }
    addUrl(link)
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    event.stopPropagation()
    takeDrop(event.dataTransfer)
  }

  async function follow(id: string, onTick: (next: ScoreJob) => void) {
    for (;;) {
      if (!alive.current) return null
      const next = await readJson<ScoreJob>(await fetch(`/audio/score/${id}`))
      if (!alive.current) return null
      onTick(next)
      if (next.status !== 'running') return next
      await new Promise((resolve) => window.setTimeout(resolve, 800))
    }
  }

  async function postScore(item: Source, chosen: ScoreSettings) {
    const res = item.kind === 'url'
      ? await fetch('/audio/score', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: item.url, settings: chosen, rights: true }),
      })
      : await fetch('/audio/score/file', {
        method: 'POST',
        headers: {
          'X-Audio-Name': encodeURIComponent(item.file.name),
          'X-Audio-Settings': JSON.stringify(chosen),
          'X-Audio-Rights': 'confirmed',
        },
        body: item.file,
      })
    return readJson<ScoreJob>(res)
  }

  async function runOne(item: Source, chosen: ScoreSettings, onTick: (next: ScoreJob) => void) {
    const startedJob = await postScore(item, chosen)
    onTick(startedJob)
    const finished = await follow(startedJob.id, onTick)
    if (finished?.status === 'error') {
      sfx.error()
      toast.error(finished.error || 'The loop failed.')
    }
    return finished
  }

  async function onSpeak(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    if (!speak.text.trim()) {
      toast.error('Type a line first.')
      return
    }
    if (speak.seed.trim() && !/^\d+$/.test(speak.seed.trim())) {
      toast.error('Seed has to be a whole number.')
      return
    }
    setBusy(true)
    try {
      const res = await fetch('/audio/speech', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: speak.text,
          pitch: speak.pitch,
          speed: speak.speed,
          variation: speak.variation,
          length: speak.length,
          drop: speak.drop,
          pauses: speak.pauses,
          brightness: speak.brightness,
          lift: speak.lift,
          tone: speak.tone,
          seed: speak.seed.trim() === '' ? null : Number(speak.seed),
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { error?: string }
        throw new Error(body.error || 'Could not speak that line.')
      }
      const blob = await res.blob()
      sfx.pop()
      const next = URL.createObjectURL(blob)
      setClip((current) => {
        if (current) URL.revokeObjectURL(current)
        return next
      })
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Could not speak that line.')
    } finally {
      setBusy(false)
    }
  }

  async function onScore(event: FormEvent) {
    event.preventDefault()
    if (busy || !source || !rights) return
    sfx.pop()
    setBusy(true)
    try {
      const done = await runOne(source, settings, (next) => {
        setJob(next)
      })
      if (done?.status === 'done') celebrate(stageRef.current)
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Could not start the loop.')
    } finally {
      setBusy(false)
    }
  }

  async function onBatch(event: FormEvent) {
    event.preventDefault()
    if (busy || !items.length || !rights) return
    setBusy(true)
    setStarted(true)
    sfx.pop()
    const chosen = settings
    const queued = items
    let made = 0
    try {
      for (const item of queued) {
        if (!alive.current) return
        setActiveKey(item.key)
        const done = await runOne(item.source, chosen, (next) => {
          setItems((current) => current.map((row) => row.key === item.key ? { ...row, job: next } : row))
        })
        if (done?.status === 'done') made += 1
      }
      if (made) celebrate(stageRef.current, 80 + made * 10)
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Could not start the batch.')
    } finally {
      setActiveKey(null)
      setBusy(false)
    }
  }

  async function retry(item: BatchItem) {
    if (busy) return
    setBusy(true)
    setActiveKey(item.key)
    try {
      await runOne(item.source, settings, (next) => {
        setItems((current) => current.map((row) => row.key === item.key ? { ...row, job: next } : row))
      })
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Could not retry that loop.')
    } finally {
      setActiveKey(null)
      setBusy(false)
    }
  }

  const sourceName = source?.kind === 'file' ? source.name : source ? sourceLabel(source.url) : ''
  const waiting = items.length > 0 && items.every((item) => !item.job)
  const voice = voiceOf(speak)
  const advSpeak = (name: keyof Voice) => SPEAK_DEFAULT[name]

  return (
    <div className="app">
      <Toasts />
      <StudioHeader builder="music" mode={mode === 'speech' ? 'one' : mode} label={speech ? 'Audio Builder · Beep speech' : undefined}>
        {busy && !speech && (
          <p className="status" role="status" aria-live="polite">
            {batch ? 'Working through the set list.' : job?.stage ? stageText(job.stage) : 'Starting the loop.'}
          </p>
        )}
      </StudioHeader>
      <div className="workspace">
        <form ref={formRef} onSubmit={speech ? onSpeak : batch ? onBatch : onScore}>
          <div className="rail-body">
            {speech && (
              <>
              <fieldset>
                <legend>Line</legend>
                <div className="line-box">
                  <textarea
                    className="line"
                    value={speak.text}
                    maxLength={600}
                    placeholder={LINES[0]}
                    aria-label="Line to speak"
                    disabled={busy}
                    onChange={(event) => patchSpeak({ text: event.target.value })}
                  />
                  <span className={speak.text.length > 540 ? 'char-count hot' : 'char-count'}>{speak.text.length} / 600</span>
                </div>
                <button
                  type="button"
                  className="text-link"
                  disabled={busy}
                  onClick={() => {
                    sfx.tap()
                    const others = LINES.filter((line) => line !== speak.text)
                    patchSpeak({ text: others[Math.floor(Math.random() * others.length)] })
                  }}
                >
                  <Megaphone aria-hidden="true" /> Give me a line
                </button>
              </fieldset>
              <fieldset>
                <legend>Voice</legend>
                <div className="chips" role="group" aria-label="Voice presets">
                  {VOICES.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="chip"
                      aria-pressed={voice === item.id}
                      disabled={busy}
                      onClick={() => {
                        sfx.tap()
                        patchSpeak(item.voice)
                      }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <RangeField id="pitch" label="Pitch" value={speak.pitch} reset={advSpeak('pitch')} min={150} max={450} step={10} text={`${speak.pitch} Hz`} disabled={busy} onChange={(value) => patchSpeak({ pitch: value })} />
                <RangeField id="speed" label="Speed" value={speak.speed} reset={advSpeak('speed')} min={6} max={28} step={1} text={`${speak.speed}/s`} disabled={busy} onChange={(value) => patchSpeak({ speed: value })} />
                <RangeField id="variation" label="Variation" value={speak.variation} reset={advSpeak('variation')} min={0} max={8} step={1} text={`${speak.variation} st`} disabled={busy} onChange={(value) => patchSpeak({ variation: value })} />
                <details className="advanced">
                  <summary>Advanced</summary>
                  <div className="advanced-body">
                    <RangeField id="length" label="Length" value={speak.length} reset={advSpeak('length')} min={0.4} max={2} step={0.1} text={`${speak.length.toFixed(1)}×`} disabled={busy} onChange={(value) => patchSpeak({ length: value })} />
                    <RangeField id="drop" label="Drop" value={speak.drop} reset={advSpeak('drop')} min={0} max={3} step={0.1} text={`${speak.drop.toFixed(1)}×`} disabled={busy} onChange={(value) => patchSpeak({ drop: value })} />
                    <RangeField id="pauses" label="Pauses" value={speak.pauses} reset={advSpeak('pauses')} min={0} max={2.5} step={0.1} text={`${speak.pauses.toFixed(1)}×`} disabled={busy} onChange={(value) => patchSpeak({ pauses: value })} />
                    <RangeField id="brightness" label="Brightness" value={speak.brightness} reset={advSpeak('brightness')} min={1500} max={10000} step={100} text={`${(speak.brightness / 1000).toFixed(1)} kHz`} disabled={busy} onChange={(value) => patchSpeak({ brightness: value })} />
                    <RangeField id="lift" label="Lift" value={speak.lift} reset={advSpeak('lift')} min={0} max={3} step={0.1} text={`${speak.lift.toFixed(1)}×`} disabled={busy} onChange={(value) => patchSpeak({ lift: value })} />
                    <RangeField id="tone" label="Tone" value={speak.tone} reset={advSpeak('tone')} min={0.1} max={0.8} step={0.05} text={`${Math.round(speak.tone * 100)}%`} disabled={busy} onChange={(value) => patchSpeak({ tone: value })} />
                    <p className="source-note">Drop is the little fall on each letter. Lift is how much ? and ! climb. Tone is how square the blip is.</p>
                  </div>
                </details>
                <div className="field">
                  <label htmlFor="seed">Seed</label>
                  <div className="url-add">
                    <input
                      id="seed"
                      type="text"
                      inputMode="numeric"
                      placeholder="Same line, same babble"
                      value={speak.seed}
                      disabled={busy}
                      onChange={(event) => patchSpeak({ seed: event.target.value })}
                    />
                    <button
                      type="button"
                      className="ghost icon-only roll"
                      aria-label="Roll a seed"
                      title="Roll a seed"
                      disabled={busy}
                      onClick={(event) => {
                        sfx.tap()
                        event.currentTarget.classList.remove('rolled')
                        void event.currentTarget.offsetWidth
                        event.currentTarget.classList.add('rolled')
                        patchSpeak({ seed: String(Math.floor(Math.random() * 1_000_000)) })
                      }}
                    >
                      <Dices aria-hidden="true" />
                    </button>
                  </div>
                </div>
              </fieldset>
              </>
            )}
            {!speech && (
              <>
                <div className="group">
                  <div className="label-row spread">
                    <span className="kicker">Recording</span>
                    {batch && <span className="count">{items.length} / {MAX_BATCH}</span>}
                  </div>
                  {batch && (
                    <div className="url-add">
                      <input
                        type="text"
                        value={urlDraft}
                        placeholder="https://…"
                        aria-label="Recording address"
                        disabled={busy}
                        onChange={(event) => setUrlDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key !== 'Enter') return
                          event.preventDefault()
                          addUrl()
                        }}
                      />
                      <button type="button" className="ghost" disabled={busy || !urlDraft.trim()} onClick={() => addUrl()}>Add</button>
                    </div>
                  )}
                  {sourceName && !batch && (
                    <div className="source-file reveal" key={sourceName}>
                      {source?.kind === 'url' ? <Link2 aria-hidden="true" /> : <FileAudio aria-hidden="true" />}
                      <span>{sourceName}</span>
                    </div>
                  )}
                  {(batch || !sourceName) && (
                    <button
                      type="button"
                      className={hot ? 'add hot' : 'add'}
                      disabled={busy}
                      onClick={() => { if (batch) fileRef.current?.click(); else openSheet() }}
                      onDragOver={(event) => {
                        event.preventDefault()
                        setHot(true)
                      }}
                      onDragLeave={() => setHot(false)}
                      onDrop={onDrop}
                    >
                      {batch ? <ListMusic aria-hidden="true" /> : <Music aria-hidden="true" />}
                      {batch ? 'Add audio or video files' : 'Add an audio or video file'}
                      <span>{batch ? 'or drop them anywhere' : 'or drop one anywhere'}</span>
                    </button>
                  )}
                  <input
                    ref={fileRef}
                    type="file"
                    accept="audio/*,video/*,.mp3,.mp4,.m4a,.wav,.ogg,.webm,.flac,.mov"
                    multiple={batch}
                    hidden
                    onChange={(event) => {
                      takeFiles([...(event.target.files ?? [])])
                      event.target.value = ''
                    }}
                  />
                  {sourceName && !batch && (
                    <div className="source-links">
                      <button type="button" disabled={busy} onClick={openSheet}>Change recording</button>
                      <button type="button" disabled={busy} onClick={() => { setSource(null); setJob(null) }}>Clear</button>
                    </div>
                  )}
                  {batch && items.length > 0 && (
                    <ul className="queue">
                      <AnimatePresence initial={false}>
                        {items.map((item) => (
                          <motion.li
                            key={item.key}
                            className="queue-row"
                            layout
                            initial={{ opacity: 0, x: -12 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 16, transition: { duration: 0.14 } }}
                          >
                            <span className="queue-mark">{item.source.kind === 'url' ? <Link2 aria-hidden="true" /> : <FileAudio aria-hidden="true" />}</span>
                            <span className="queue-name">{item.name}</span>
                            <button
                              type="button"
                              className="icon-btn small"
                              aria-label="Remove"
                              disabled={busy}
                              onClick={() => {
                                sfx.tap()
                                setItems((current) => current.filter((row) => row.key !== item.key))
                              }}
                            >
                              <X />
                            </button>
                          </motion.li>
                        ))}
                      </AnimatePresence>
                    </ul>
                  )}
                </div>
                <fieldset>
                  <legend>Loop</legend>
                  <div className="field">
                    <span className="kicker">Style</span>
                    <Segment
                      label="Style"
                      options={[{ value: 'soft', label: 'Soft' }, { value: 'gb', label: '8-bit' }] as const}
                      value={settings.style}
                      disabled={busy}
                      onChange={(style) => patchScore({ style })}
                    />
                  </div>
                  <div className="field">
                    <span className="kicker">Takes</span>
                    <Segment
                      label="Takes"
                      options={[{ value: 1, label: '1' }, { value: 2, label: '2' }, { value: 3, label: '3' }] as const}
                      value={settings.takes as 1 | 2 | 3}
                      disabled={busy}
                      onChange={(takes) => patchScore({ takes })}
                    />
                  </div>
                  <p className="source-note">More takes try other sections of the song, best seam first. A song with fewer good sections returns fewer.</p>
                  <PickField
                    label="Lead"
                    value={settings.lead}
                    options={LEAD_OPTIONS}
                    disabled={busy}
                    onChange={(value) => patchScore({ lead: value })}
                  />
                  <p className="source-note">Sung notes replay the tune on an instrument. The recording of the voice is never in the file.</p>
                  <RangeField id="min_seconds" label="Shortest loop" value={settings.min_seconds} reset={SCORE_DEFAULT.min_seconds} min={8} max={90} step={1} text={`${settings.min_seconds}s`} disabled={busy} onChange={(value) => patchScore({ min_seconds: value })} />
                  <RangeField id="max_seconds" label="Longest loop" value={settings.max_seconds} reset={SCORE_DEFAULT.max_seconds} min={15} max={180} step={1} text={`${settings.max_seconds}s`} disabled={busy} onChange={(value) => patchScore({ max_seconds: value })} />
                  <RangeField id="start_after" label="Start after" value={settings.start_after} reset={SCORE_DEFAULT.start_after} min={0} max={180} step={1} text={`${settings.start_after}s`} disabled={busy} onChange={(value) => patchScore({ start_after: value })} />
                  <div className="toggles">
                    <Toggle checked={settings.classic} disabled={busy} onChange={(classic) => patchScore({ classic })}>Classic mix</Toggle>
                  </div>
                  <p className="source-note">Classic skips the key snap, arpeggiates faster, and puts on a heavier echo.</p>
                  <details className="advanced">
                    <summary>Advanced</summary>
                    <div className="advanced-body">
                      <RangeField id="space" label="Space" value={settings.space} reset={1} min={0} max={2} step={0.1} text={times(settings.space)} disabled={busy} onChange={(value) => patchScore({ space: value })} />
                      <RangeField id="loop-brightness" label="Brightness" value={settings.brightness} reset={1} min={0.4} max={1.6} step={0.1} text={times(settings.brightness)} disabled={busy} onChange={(value) => patchScore({ brightness: value })} />
                      <RangeField id="lead-level" label="Lead" value={settings.lead_level} reset={1} min={0} max={2} step={0.1} text={times(settings.lead_level)} disabled={busy} onChange={(value) => patchScore({ lead_level: value })} />
                      <RangeField id="chords-level" label="Chords" value={settings.chords_level} reset={1} min={0} max={2} step={0.1} text={times(settings.chords_level)} disabled={busy} onChange={(value) => patchScore({ chords_level: value })} />
                      <RangeField id="bass-level" label="Bass" value={settings.bass_level} reset={1} min={0} max={2} step={0.1} text={times(settings.bass_level)} disabled={busy} onChange={(value) => patchScore({ bass_level: value })} />
                      <RangeField id="drums-level" label="Drums" value={settings.drums_level} reset={1} min={0} max={2} step={0.1} text={times(settings.drums_level)} disabled={busy} onChange={(value) => patchScore({ drums_level: value })} />
                      <p className="source-note">Space is the room on Soft, and the echo on 8-bit. These levels set the starting mix for the next loop. Use the mixer to balance one you already made.</p>
                    </div>
                  </details>
                </fieldset>
              </>
            )}
          </div>
          <div className="dock">
            <p className="source-note dock-note">Runs locally. No vocals, no OpenRouter charge.</p>
            {!speech && (
              <label className="rights">
                <input type="checkbox" checked={rights} disabled={busy} onChange={(event) => { sfx.tap(); setRightsFor(event.target.checked ? recordings : null) }} />
                <span>{batch ? 'I own these recordings or have permission to use them.' : 'I own this recording or have permission to use it.'}</span>
              </label>
            )}
            {batch && started && !busy && (
              <button
                type="button"
                className="ghost apply"
                onClick={() => {
                  setItems([])
                  setStarted(false)
                }}
              >
                New batch
              </button>
            )}
            <button type="submit" className={busy ? 'make busy' : 'make shine'} disabled={busy || (!speech && (!rights || (batch ? items.length === 0 : !source)))}>
              {busy
                ? <><span className="dots" aria-hidden="true"><i /><i /><i /></span> Working</>
                : <>{speech ? <Megaphone aria-hidden="true" /> : <Music aria-hidden="true" />} {speech ? 'Speak' : batch ? 'Make batch' : 'Make loop'} <Shortcut /></>}
            </button>
          </div>
        </form>
        <section className="stage" aria-label="Audio" ref={stageRef}>
          {speech && !clip && !busy && (
            <EmptyState title="Say something silly." art={<BubbleScene talking={false} />}>
              <p>The blob has been practicing. Type a line and press Speak. It comes out as babble. Not a person, and not a singer.</p>
              <p>Pick a voice to start from. Grump is a crowd favorite.</p>
            </EmptyState>
          )}
          {speech && (clip || busy) && (
            <div className="music-well">
              <div className="well speech-well">
                <BubbleScene talking={busy || talking} />
                {busy
                  ? <p className="source-note">Clearing its throat.</p>
                  : clip && (
                    <audio
                      key={clip}
                      className="score"
                      src={clip}
                      controls
                      autoPlay
                      onPlay={() => setTalking(true)}
                      onPause={() => setTalking(false)}
                      onEnded={() => setTalking(false)}
                    />
                  )}
              </div>
              {clip && !busy && <a className="ghost with-icon" href={clip} download="beep-speech.wav"><Download aria-hidden="true" /> Download wav</a>}
            </div>
          )}
          {!speech && !batch && !source && !job && !busy && (
            <EmptyState title="The tape is napping." art={<TapeScene />}>
              <p>Wake it up with an audio or video file, then Make loop. What comes back can play forever, and the voice is never in it.</p>
              <p>Nothing starts from the drop. You can drop anywhere, though. The tape is a light sleeper.</p>
            </EmptyState>
          )}
          {!speech && !batch && (job || busy) && (
            <div className="music-well">
              {job?.status === 'running' || (busy && !job) ? (
                <div className="well working">
                  <div className="orb-help">
                    <ThinkingOrb state={STAGE_ORB[job?.stage || 'queued'] ?? 'weaving'} size={64} theme="dark" aria-label={stageText(job?.stage || 'queued')} />
                    <p>{job?.stage ? stageText(job.stage) : 'Starting the loop.'}</p>
                  </div>
                </div>
              ) : job?.files.wav && (
                <>
                  <div className="piece reveal">
                    <p>{job.name}</p>
                  </div>
                  <TakeView key={job.id} job={job} />
                </>
              )}
              {job?.status === 'error' && <p className="is-error">{job.error || 'The loop failed.'}</p>}
            </div>
          )}
          {batch && !started && (
            <EmptyState title={waiting ? 'Ready when you are.' : 'A set list of none.'} art={<ShelfScene />}>
              <p>
                {waiting
                  ? 'Make batch runs them one at a time. Nothing starts from the drop. The voice stays out of every file.'
                  : 'The whole shelf is asleep. Add audio or video files, then Make batch. They run one at a time on this machine, and the singing stays out.'}
              </p>
            </EmptyState>
          )}
          {batch && started && (
            <ul className="results">
              {items.map((item, index) => {
                const row = item.job
                const orb = row?.status === 'running'
                  ? STAGE_ORB[row.stage] ?? 'weaving'
                  : !row && busy && item.key === activeKey
                    ? 'connecting' as const
                    : null
                return (
                  <motion.li
                    key={item.key}
                    className={row?.status === 'error' ? 'result error' : row?.status === 'done' ? 'result done' : 'result'}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ type: 'spring', stiffness: 360, damping: 28, delay: Math.min(index, 8) * 0.04 }}
                  >
                    <div className="thumb">
                      {orb
                        ? <ThinkingOrb state={orb} size={64} theme="dark" aria-label={row ? stageText(row.stage) : 'Waiting'} />
                        : row?.status === 'done'
                          ? <span className="queue-mark"><Music aria-hidden="true" /></span>
                          : <NapScene />}
                    </div>
                    <div className="result-copy">
                      <p className="queue-name">{row?.name || item.name}</p>
                      {row?.status === 'running' && <p className="source-note">{stageText(row.stage)}</p>}
                      {row?.status === 'error' && <p className="is-error">{row.error || 'The loop failed.'}</p>}
                      {row?.status === 'done' && <TakeView key={row.id} job={row} batch />}
                      {row?.status === 'error' && (
                        <div className="result-actions">
                          <button type="button" className="ghost" disabled={busy} onClick={() => void retry(item)}>Retry</button>
                        </div>
                      )}
                    </div>
                  </motion.li>
                )
              })}
            </ul>
          )}
        </section>
      </div>
      <DropVeil
        enabled={!speech && !busy && !sheet}
        title={batch ? 'Toss them on the shelf.' : 'Feed the tape.'}
        hint="Audio, video, or a link. Nothing starts from the drop."
        onDrop={takeDrop}
      />
      <Sheet
        open={sheet && !batch}
        onClose={closeSheet}
        labelledBy="intake-title"
        drop={{
          onDragOver: (event) => {
            event.preventDefault()
            setSheetHot(true)
          },
          onDragLeave: (event) => {
            if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
            setSheetHot(false)
          },
          onDrop,
        }}
      >
        <h2 id="intake-title">Add a recording</h2>
        <p>Choose a file, drop one, or paste a URL.</p>
        <div className={sheetHot ? 'dropwell hot' : 'dropwell'}>
          <button type="button" className="make" onClick={() => fileRef.current?.click()}>Choose a file</button>
          <p>or drop it here</p>
        </div>
        <label htmlFor="sheet-url">Recording address</label>
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
            addUrl(sheetUrl)
          }}
        />
        {sheetError && <p className="is-error shake" key={sheetError}>{sheetError}</p>}
        <div className="source-row">
          <button type="button" className="ghost" onClick={() => addUrl(sheetUrl)}>Use URL</button>
          <button type="button" className="ghost" onClick={closeSheet}>Cancel</button>
        </div>
      </Sheet>
    </div>
  )
}

function times(value: number) {
  return `${value.toFixed(1)}×`
}

function TakeView({ job, batch = false }: { job: ScoreJob; batch?: boolean }) {
  const [number, setNumber] = useState(1)
  const [switched, setSwitched] = useState(false)
  const [strips, setStrips] = useState<Strips>({})
  const takes = job.takes ?? []
  const take = takes.find((item) => item.number === number) ?? takes[0]
  const files = take?.files ?? job.files
  const info = take?.info ?? job.info
  if (!files.wav) return null
  const download = files.zip && (
    <a className={batch ? 'ghost with-icon' : 'make shine download'} href={files.zip} download>
      <Download aria-hidden="true" /> {batch ? 'Download' : 'Download package'}
    </a>
  )
  return (
    <>
      {info && <p className={batch ? 'source-note' : 'score-meta'}>{scoreLine(info)}</p>}
      {takes.length > 1 && (
        <Segment
          label="Take"
          options={takes.map((item) => ({ value: item.number, label: `Take ${item.number}` }))}
          value={take?.number ?? 1}
          onChange={(next) => {
            setNumber(next)
            setSwitched(true)
          }}
        />
      )}
      <TrackList
        key={files.wav}
        mix={files.wav}
        tracks={files.tracks ?? []}
        name={take && take.number > 1 ? `${job.name}-take${take.number}` : job.name}
        strips={strips}
        onStrips={setStrips}
        autoPlay={!batch || switched}
        keep={!batch}
      />
      {!batch && files.tracks && files.tracks.length > 0 && (
        <p className="source-note">Each part lines up with the loop. The package is those parts, the notes as MIDI, the settings, and the finished mix, ready for a studio.</p>
      )}
      {batch ? <div className="result-actions">{download}</div> : download}
    </>
  )
}

function PickField({
  label, value, options, disabled, onChange,
}: {
  label: string
  value: Lead
  options: { value: Lead; label: string }[]
  disabled: boolean
  onChange: (value: Lead) => void
}) {
  const [open, setOpen] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLUListElement>(null)
  const current = options.find((option) => option.value === value)

  useLayoutEffect(() => {
    if (!open) return
    const menu = menuRef.current
    const button = buttonRef.current
    if (!menu || !button) return
    const rect = button.getBoundingClientRect()
    const height = menu.offsetHeight
    const below = window.innerHeight - rect.bottom
    const top = below < height + 8 && rect.top > height + 8 ? rect.top - height - 4 : rect.bottom + 4
    menu.style.top = `${top}px`
    menu.style.left = `${rect.left}px`
    menu.style.width = `${rect.width}px`
  }, [open])

  useEffect(() => {
    if (!open) return
    const onPointer = (event: PointerEvent) => {
      const target = event.target
      if (!(target instanceof Node)) return
      if (buttonRef.current?.contains(target) || menuRef.current?.contains(target)) return
      setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="field pick">
      <span className="kicker" id="lead-label">{label}</span>
      <button
        ref={buttonRef}
        type="button"
        className="pick-button"
        aria-labelledby="lead-label"
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((currentOpen) => !currentOpen)}
      >
        {current?.label}
      </button>
      {open && (
        <ul className="pick-menu" role="listbox" aria-labelledby="lead-label" ref={menuRef}>
          {options.map((option) => (
            <li key={option.value}>
              <button
                type="button"
                role="option"
                aria-selected={option.value === value}
                onClick={() => {
                  onChange(option.value)
                  setOpen(false)
                }}
              >
                {option.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
