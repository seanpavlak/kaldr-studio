import { useEffect, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from 'react'
import { Download, Pause, Play } from 'lucide-react'

export type LoopTrack = { id: string; label: string; wav: string }
export type Strip = { level: number; mute: boolean; solo: boolean }
export type Strips = Record<string, Strip>

type Peaks = { min: Float32Array; max: Float32Array; duration: number }
type Buffers = Record<string, AudioBuffer>

const WAVE_BINS = 480
// The rate loops are made at. Decoding at it keeps every sample, so the loop point stays exact.
const SAMPLE_RATE = 44100
// The level a finished loop is delivered at. A louder mix comes down to it.
const CEILING = 0.89
const PEAK_STRIDE = 16
const START_DELAY = 0.04
const FADER_MAX = 1.5
const OPEN: Strip = { level: 1, mute: false, solo: false }

function clock(seconds: number) {
  const whole = Math.max(0, Math.floor(seconds))
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`
}

function peaksFrom(buffer: AudioBuffer, bins: number): Peaks {
  const data = buffer.getChannelData(0)
  const min = new Float32Array(bins)
  const max = new Float32Array(bins)
  const size = Math.max(1, Math.floor(data.length / bins))
  for (let i = 0; i < bins; i++) {
    let lo = 0
    let hi = 0
    const start = i * size
    const end = Math.min(data.length, start + size)
    for (let j = start; j < end; j++) {
      const sample = data[j]
      if (sample < lo) lo = sample
      if (sample > hi) hi = sample
    }
    min[i] = lo
    max[i] = hi
  }
  return { min, max, duration: buffer.duration }
}

function drawWave(canvas: HTMLCanvasElement, peaks: Peaks | undefined, color: string) {
  const width = canvas.clientWidth
  const height = canvas.clientHeight
  if (!width || !height) return
  const ratio = window.devicePixelRatio || 1
  canvas.width = Math.floor(width * ratio)
  canvas.height = Math.floor(height * ratio)
  const pen = canvas.getContext('2d')
  if (!pen) return
  pen.setTransform(ratio, 0, 0, ratio, 0, 0)
  pen.clearRect(0, 0, width, height)
  const mid = height / 2
  pen.fillStyle = color
  if (!peaks) {
    pen.fillRect(0, mid, width, 1)
    return
  }
  const bar = width / peaks.min.length
  for (let i = 0; i < peaks.min.length; i++) {
    const top = mid + peaks.min[i] * height * 0.46
    const bottom = mid + peaks.max[i] * height * 0.46
    const y = Math.min(top, bottom)
    pen.fillRect(i * bar, y, Math.max(bar - 0.35, 0.6), Math.max(1, Math.abs(bottom - top)))
  }
}

function stripOf(strips: Strips, id: string) {
  return strips[id] ?? OPEN
}

/** What a part plays at: a soloed part wins over the others, and mute wins over solo. */
function gainOf(strips: Strips, id: string, ids: string[]) {
  const strip = stripOf(strips, id)
  const anySolo = ids.some((other) => stripOf(strips, other).solo)
  return strip.mute || (anySolo && !strip.solo) ? 0 : strip.level
}

function loudest(parts: { data: Float32Array[]; gain: number }[], stride: number) {
  const playing = parts.filter((part) => part.gain > 0)
  if (!playing.length) return 0
  let peak = 0
  const frames = playing[0].data[0].length
  for (let channel = 0; channel < playing[0].data.length; channel++) {
    for (let i = 0; i < frames; i += stride) {
      let sum = 0
      for (const part of playing) sum += part.data[channel][i] * part.gain
      const size = Math.abs(sum)
      if (size > peak) peak = size
    }
  }
  return peak
}

function channelsOf(buffer: AudioBuffer) {
  return Array.from({ length: buffer.numberOfChannels }, (_, channel) => buffer.getChannelData(channel))
}

function wavFrom(channels: Float32Array[], rate: number) {
  const frames = channels[0].length
  const count = channels.length
  const size = frames * count * 2
  const view = new DataView(new ArrayBuffer(44 + size))
  const text = (at: number, value: string) => {
    for (let i = 0; i < value.length; i++) view.setUint8(at + i, value.charCodeAt(i))
  }
  text(0, 'RIFF')
  view.setUint32(4, 36 + size, true)
  text(8, 'WAVEfmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, count, true)
  view.setUint32(24, rate, true)
  view.setUint32(28, rate * count * 2, true)
  view.setUint16(32, count * 2, true)
  view.setUint16(34, 16, true)
  text(36, 'data')
  view.setUint32(40, size, true)
  let at = 44
  for (let i = 0; i < frames; i++) {
    for (let channel = 0; channel < count; channel++) {
      const sample = Math.max(-1, Math.min(1, channels[channel][i]))
      view.setInt16(at, Math.round(sample * 32767), true)
      at += 2
    }
  }
  return new Blob([view], { type: 'audio/wav' })
}

// One loop sounds at a time, so a batch page never stacks them or holds every part in memory.
let stopPlaying: (() => void) | null = null

export function TrackList({ mix, tracks, name, strips, onStrips, autoPlay = false, keep = false }: {
  mix: string
  tracks: LoopTrack[]
  name: string
  strips: Strips
  onStrips: (next: (current: Strips) => Strips) => void
  autoPlay?: boolean
  /** Hold the decoded parts after drawing them. For a page that shows one loop, not many. */
  keep?: boolean
}) {
  const lanes = [{ id: 'mix', label: 'Loop', wav: mix }, ...tracks]
  const laneKey = lanes.map((lane) => lane.wav).join('|')
  const parts = tracks.length ? tracks : lanes
  const partIds = parts.map((part) => part.id)
  const mixable = tracks.length > 0
  const [peaks, setPeaks] = useState<Record<string, Peaks>>({})
  const [playing, setPlaying] = useState(false)
  const [duration, setDuration] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const headRef = useRef<HTMLDivElement>(null)
  const clockRef = useRef<HTMLSpanElement>(null)
  const waveRef = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)
  const offset = useRef(0)
  const anchor = useRef(0)
  const live = useRef(false)
  const context = useRef<AudioContext | null>(null)
  const master = useRef<GainNode | null>(null)
  const gains = useRef<Record<string, GainNode>>({})
  const sources = useRef<AudioBufferSourceNode[]>([])
  const buffers = useRef<Buffers | null>(null)
  const stripsRef = useRef(strips)
  const stopRef = useRef<() => void>(() => {})
  // Kept for this mixer's whole life, so it can be compared against the page's one playing loop.
  const [stopThis] = useState(() => () => stopRef.current())

  async function decode(signal?: AbortSignal) {
    const decoder = new OfflineAudioContext(2, 1, SAMPLE_RATE)
    const found: Buffers = {}
    await Promise.all(lanes.map(async (lane) => {
      try {
        const res = await fetch(lane.wav, { signal })
        if (!res.ok) return
        found[lane.id] = await decoder.decodeAudioData(await res.arrayBuffer())
      } catch {
        // A missing part still leaves its lane.
      }
    }))
    return found
  }

  /** The master level that keeps this mix from clipping. It stays at 1 until the parts need it. */
  function headroom(found: Buffers, current: Strips) {
    const peak = loudest(
      partIds.filter((id) => found[id]).map((id) => ({ data: channelsOf(found[id]), gain: gainOf(current, id, partIds) })),
      PEAK_STRIDE,
    )
    return peak > CEILING ? CEILING / peak : 1
  }

  function now() {
    const ctx = context.current
    if (!live.current || !ctx || duration <= 0) return offset.current
    const elapsed = ctx.currentTime - anchor.current
    return elapsed <= 0 ? offset.current : elapsed % duration
  }

  function silence() {
    for (const source of sources.current) {
      try { source.stop() } catch { /* it never started */ }
      source.disconnect()
    }
    sources.current = []
    live.current = false
  }

  function launch(from: number) {
    const ctx = context.current
    const found = buffers.current
    if (!ctx || !found) return
    silence()
    const when = ctx.currentTime + START_DELAY
    for (const id of partIds) {
      const buffer = found[id]
      if (!buffer) continue
      const source = ctx.createBufferSource()
      source.buffer = buffer
      source.loop = true
      source.connect(gains.current[id])
      source.start(when, Math.min(from, buffer.duration - 0.001))
      sources.current.push(source)
    }
    offset.current = from
    anchor.current = when - from
    live.current = true
  }

  function pause() {
    offset.current = now()
    silence()
    setPlaying(false)
  }

  // Refreshed each render, so the page's one playing loop always stops through current state.
  useEffect(() => {
    stopRef.current = () => {
      pause()
      if (!keep) buffers.current = null
    }
  })

  async function play() {
    if (stopPlaying && stopPlaying !== stopThis) stopPlaying()
    stopPlaying = stopThis
    let ctx = context.current
    if (!ctx) {
      ctx = new AudioContext({ sampleRate: SAMPLE_RATE })
      context.current = ctx
      master.current = ctx.createGain()
      master.current.connect(ctx.destination)
      for (const id of partIds) {
        const gain = ctx.createGain()
        gain.gain.value = gainOf(stripsRef.current, id, partIds)
        gain.connect(master.current)
        gains.current[id] = gain
      }
    }
    // A page that opens without a click has no permission to sound yet. It waits for the play button.
    await Promise.race([ctx.resume().catch(() => {}), new Promise((resolve) => window.setTimeout(resolve, 200))])
    if (ctx.state !== 'running' || stopPlaying !== stopThis) return
    if (!buffers.current) buffers.current = await decode()
    if (stopPlaying !== stopThis || context.current !== ctx) return
    if (master.current) master.current.gain.value = headroom(buffers.current, stripsRef.current)
    launch(offset.current)
    setPlaying(true)
  }

  useEffect(() => {
    const ctrl = new AbortController()
    let gone = false
    void decode(ctrl.signal).then((found) => {
      if (gone) return
      const drawn: Record<string, Peaks> = {}
      for (const [id, buffer] of Object.entries(found)) drawn[id] = peaksFrom(buffer, WAVE_BINS)
      setPeaks(drawn)
      if (found.mix) setDuration(found.mix.duration)
      if (keep || autoPlay) buffers.current = found
      if (autoPlay) void play()
    })
    return () => {
      gone = true
      ctrl.abort()
    }
    // laneKey already covers the wav addresses this effect loads, and a new one means a new mixer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [laneKey])

  useEffect(() => () => {
    silence()
    if (stopPlaying === stopThis) stopPlaying = null
    void context.current?.close().catch(() => {})
    context.current = null
    // Only ever runs as this mixer goes away.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    const draw = () => {
      root.querySelectorAll<HTMLCanvasElement>('canvas[data-lane]').forEach((canvas) => {
        const id = canvas.dataset.lane || ''
        drawWave(canvas, peaks[id], id === 'mix' ? '#e4a15a' : '#7d6a55')
      })
    }
    draw()
    const observer = new ResizeObserver(draw)
    observer.observe(root)
    return () => observer.disconnect()
  }, [peaks, laneKey])

  useEffect(() => {
    stripsRef.current = strips
    const ctx = context.current
    if (!ctx) return
    for (const id of partIds) {
      gains.current[id]?.gain.setTargetAtTime(gainOf(strips, id, partIds), ctx.currentTime, 0.01)
    }
    if (buffers.current && master.current) {
      master.current.gain.setTargetAtTime(headroom(buffers.current, strips), ctx.currentTime, 0.01)
    }
    // The parts come from laneKey, and a new set of them means a new mixer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strips])

  useEffect(() => {
    let frame = 0
    const tick = () => {
      const wave = waveRef.current
      const head = headRef.current
      const at = now()
      if (wave && head && duration > 0) head.style.left = `${wave.offsetLeft + (at / duration) * wave.clientWidth}px`
      if (clockRef.current) clockRef.current.textContent = duration ? `${clock(at)} / ${clock(duration)}` : '0:00'
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
    // now() reads refs, and the only state it needs is duration.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [duration])

  function toggle() {
    if (playing) pause()
    else void play()
  }

  function scrubTo(clientX: number, rect: DOMRect) {
    if (rect.width <= 0 || duration <= 0) return
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
    offset.current = Math.min(Math.max(0, duration - 0.05), ratio * duration)
    // The parts restart together on release, so a drag does not chatter.
    silence()
  }

  function beginScrub(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0 || dragging.current) return
    const target = event.currentTarget
    if (target.getBoundingClientRect().width <= 0) return
    dragging.current = true
    const resume = playing
    try { target.setPointerCapture(event.pointerId) } catch { /* the window listeners still follow the pointer */ }
    scrubTo(event.clientX, target.getBoundingClientRect())
    const pointerId = event.pointerId
    const move = (ev: PointerEvent) => {
      if (ev.pointerId === pointerId) scrubTo(ev.clientX, target.getBoundingClientRect())
    }
    const finish = (ev: PointerEvent) => {
      if (ev.pointerId !== pointerId) return
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', finish)
      window.removeEventListener('pointercancel', finish)
      scrubTo(ev.clientX, target.getBoundingClientRect())
      dragging.current = false
      if (resume) launch(offset.current)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', finish)
    window.addEventListener('pointercancel', finish)
  }

  function patchStrip(id: string, patch: Partial<Strip>) {
    onStrips((current) => ({ ...current, [id]: { ...stripOf(current, id), ...patch } }))
  }

  async function downloadMix() {
    const found = buffers.current ?? await decode()
    if (!buffers.current && keep) buffers.current = found
    const present = partIds.filter((id) => found[id])
    if (!present.length) return
    const first = found[present[0]]
    const mixed = Array.from({ length: first.numberOfChannels }, () => new Float32Array(first.length))
    for (const id of present) {
      const gain = gainOf(strips, id, partIds)
      if (!gain) continue
      channelsOf(found[id]).forEach((data, channel) => {
        const out = mixed[channel]
        for (let i = 0; i < out.length; i++) out[i] += data[i] * gain
      })
    }
    const peak = loudest([{ data: mixed, gain: 1 }], 1)
    if (peak > CEILING) {
      const scale = CEILING / peak
      for (const out of mixed) for (let i = 0; i < out.length; i++) out[i] *= scale
    }
    const link = document.createElement('a')
    link.href = URL.createObjectURL(wavFrom(mixed, first.sampleRate))
    link.download = `${name}-mix.wav`
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(link.href), 10_000)
  }

  const step = duration > 60 ? 10 : duration > 20 ? 5 : 2
  const ruler = duration > 0 ? Array.from({ length: Math.floor(duration / step) + 1 }, (_, i) => i * step) : []
  const changed = partIds.some((id) => {
    const strip = stripOf(strips, id)
    return strip.level !== 1 || strip.mute || strip.solo
  })

  return (
    <div className="mixer" ref={rootRef}>
      <div className="mixer-transport">
        <button type="button" className={playing ? 'play on' : 'play'} onClick={toggle} aria-label={playing ? 'Pause' : 'Play'}>
          {playing ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
        </button>
        <span ref={clockRef}>0:00</span>
        <span className={playing ? 'eq on' : 'eq'} aria-hidden="true"><i /><i /><i /><i /></span>
        {mixable && (
          <span className="mixer-actions">
            {changed && <button type="button" className="text-link" onClick={() => onStrips(() => ({}))}>Reset mix</button>}
            <button type="button" className="ghost with-icon" onClick={() => void downloadMix()}><Download aria-hidden="true" /> This mix</button>
          </span>
        )}
      </div>
      <div className="mixer-body">
        <div className="mixer-ruler" aria-hidden="true" onPointerDown={beginScrub}>
          {ruler.map((mark) => (
            <span key={mark} style={{ left: `${(mark / duration) * 100}%` }}>{clock(mark)}</span>
          ))}
        </div>
        {lanes.map((lane) => {
          const strip = stripOf(strips, lane.id)
          const isPart = mixable && lane.id !== 'mix'
          const quiet = isPart && gainOf(strips, lane.id, partIds) === 0
          return (
            <div className={quiet ? 'lane off' : 'lane'} key={lane.id}>
              <div className="lane-strip">
                <div className="lane-head">
                  <span className="lane-name">{lane.label}</span>
                  {isPart && (
                    <>
                      <button type="button" className="lane-toggle" aria-pressed={strip.mute} aria-label={`Mute ${lane.label}`} title="Mute" onClick={() => patchStrip(lane.id, { mute: !strip.mute })}>M</button>
                      <button type="button" className="lane-toggle" aria-pressed={strip.solo} aria-label={`Solo ${lane.label}`} title="Solo" onClick={() => patchStrip(lane.id, { solo: !strip.solo })}>S</button>
                    </>
                  )}
                </div>
                {isPart && (
                  <input
                    type="range"
                    className="lane-fader"
                    min={0}
                    max={FADER_MAX}
                    step={0.01}
                    value={strip.level}
                    aria-label={`${lane.label} level`}
                    title={`${Math.round(strip.level * 100)}%. Double-click to reset.`}
                    style={{ '--fill': `${(strip.level / FADER_MAX) * 100}%` } as CSSProperties}
                    onChange={(event) => patchStrip(lane.id, { level: Number(event.target.value) })}
                    onDoubleClick={() => patchStrip(lane.id, { level: 1 })}
                  />
                )}
              </div>
              <div
                className={lane.id === 'mix' ? 'lane-wave mix' : 'lane-wave'}
                ref={lane.id === 'mix' ? waveRef : undefined}
                role="slider"
                aria-label={`${lane.label} waveform`}
                aria-valuemin={0}
                aria-valuemax={Math.round(duration)}
                onPointerDown={beginScrub}
              >
                <canvas data-lane={lane.id} />
              </div>
            </div>
          )
        })}
        <div className="playhead" ref={headRef} />
      </div>
    </div>
  )
}
