import { useSyncExternalStore } from 'react'

// Pixel confetti and tiny square-wave blips. Both stay quiet under
// prefers-reduced-motion and the header's sound switch.

const CONFETTI = ['#e4a15a', '#f6c98a', '#6fd3c1', '#a78bfa', '#f08aa0', '#f4f0e8', '#f5c542']
const SOUND_KEY = 'kaldr.sound'

function reducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

type Bit = { x: number; y: number; vx: number; vy: number; size: number; color: string; life: number; ttl: number }

let canvas: HTMLCanvasElement | null = null
let bits: Bit[] = []
let frame = 0

function surface() {
  if (!canvas) {
    canvas = document.createElement('canvas')
    canvas.className = 'confetti'
    canvas.setAttribute('aria-hidden', 'true')
    document.body.appendChild(canvas)
  }
  const ratio = window.devicePixelRatio || 1
  canvas.width = Math.floor(window.innerWidth * ratio)
  canvas.height = Math.floor(window.innerHeight * ratio)
  return canvas
}

function step() {
  const pen = canvas?.getContext('2d')
  if (!canvas || !pen) return
  const ratio = window.devicePixelRatio || 1
  pen.setTransform(ratio, 0, 0, ratio, 0, 0)
  pen.clearRect(0, 0, window.innerWidth, window.innerHeight)
  bits = bits.filter((bit) => bit.life < bit.ttl)
  for (const bit of bits) {
    bit.life += 1
    bit.vy += 0.32
    bit.vx *= 0.985
    bit.vy *= 0.985
    bit.x += bit.vx
    bit.y += bit.vy
    const fade = bit.life > bit.ttl * 0.7 ? 1 - (bit.life - bit.ttl * 0.7) / (bit.ttl * 0.3) : 1
    pen.globalAlpha = Math.max(0, fade)
    pen.fillStyle = bit.color
    // Snap to a 2px grid so the confetti reads as pixels, not glitter.
    pen.fillRect(Math.round(bit.x / 2) * 2, Math.round(bit.y / 2) * 2, bit.size, bit.size)
  }
  pen.globalAlpha = 1
  if (bits.length) frame = requestAnimationFrame(step)
  else {
    frame = 0
    pen.clearRect(0, 0, window.innerWidth, window.innerHeight)
  }
}

/** Throws a handful of pixel confetti out of an element, or the middle of the screen. */
export function burst(from?: Element | null, count = 70) {
  if (reducedMotion()) return
  surface()
  const box = from?.getBoundingClientRect()
  const cx = box ? box.left + box.width / 2 : window.innerWidth / 2
  const cy = box ? box.top + box.height / 2 : window.innerHeight / 2
  for (let i = 0; i < count; i++) {
    const angle = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.3
    const speed = 5 + Math.random() * 9
    bits.push({
      x: cx + (Math.random() - 0.5) * 24,
      y: cy + (Math.random() - 0.5) * 24,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      size: Math.random() < 0.3 ? 6 : 4,
      color: CONFETTI[Math.floor(Math.random() * CONFETTI.length)],
      life: 0,
      ttl: 60 + Math.random() * 50,
    })
  }
  if (!frame) frame = requestAnimationFrame(step)
}

const listeners = new Set<() => void>()

function readSound() {
  try {
    return window.localStorage.getItem(SOUND_KEY) !== 'off'
  } catch {
    return true
  }
}

let soundOn = typeof window === 'undefined' ? true : readSound()

export function setSound(next: boolean) {
  soundOn = next
  try {
    window.localStorage.setItem(SOUND_KEY, next ? 'on' : 'off')
  } catch {
    // Private windows can refuse storage. The switch still works for this visit.
  }
  listeners.forEach((listener) => listener())
  if (next) sfx.pop()
}

export function useSound() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => soundOn,
  )
}

let audio: AudioContext | null = null

function tone(freq: number, seconds: number, delay = 0, type: OscillatorType = 'square', level = 0.03) {
  if (!soundOn) return
  try {
    audio ??= new AudioContext()
    if (audio.state === 'suspended') void audio.resume()
    const start = audio.currentTime + delay
    const osc = audio.createOscillator()
    const gain = audio.createGain()
    osc.type = type
    osc.frequency.setValueAtTime(freq, start)
    gain.gain.setValueAtTime(level, start)
    gain.gain.exponentialRampToValueAtTime(0.0001, start + seconds)
    osc.connect(gain).connect(audio.destination)
    osc.start(start)
    osc.stop(start + seconds + 0.02)
  } catch {
    // No audio device is fine. The page is still a page.
  }
}

export const sfx = {
  tap: () => tone(740, 0.035, 0, 'square', 0.018),
  pop: () => {
    tone(880, 0.05)
    tone(1320, 0.06, 0.045)
  },
  arm: () => {
    tone(523, 0.06)
    tone(784, 0.08, 0.06)
  },
  success: () => [523, 659, 784, 1047, 1319].forEach((freq, index) => tone(freq, 0.12, index * 0.07, 'square', 0.025)),
  error: () => {
    tone(311, 0.12, 0, 'square', 0.03)
    tone(207, 0.18, 0.1, 'square', 0.03)
  },
}

/** Confetti and the happy jingle, together. */
export function celebrate(from?: Element | null, count?: number) {
  burst(from, count)
  sfx.success()
}
