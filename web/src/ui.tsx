import { useEffect, useId, useRef, useState, type CSSProperties, type DragEvent, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Download, Volume2, VolumeX } from 'lucide-react'
import { Toaster } from 'sonner'
import 'sonner/dist/styles.css'
import { celebrate, setSound, sfx, useSound } from './fx.ts'
import { ChompScene, PayBlob } from './pixel.tsx'

const SPRING = { type: 'spring', stiffness: 460, damping: 34 } as const

export function Toasts() {
  return <Toaster theme="dark" position="bottom-right" offset={16} toastOptions={{ className: 'toast' }} />
}

export function SoundToggle() {
  const on = useSound()
  return (
    <button
      type="button"
      className="icon-btn"
      aria-pressed={on}
      aria-label={on ? 'Turn interface sounds off' : 'Turn interface sounds on'}
      title={on ? 'Sounds on' : 'Sounds off'}
      onClick={() => setSound(!on)}
    >
      {on ? <Volume2 /> : <VolumeX />}
    </button>
  )
}

export function RangeField({
  id, label, value, min, max, step, text, title, reset, disabled = false, onChange,
}: {
  id: string
  label: string
  value: number
  min: number
  max: number
  step: number
  text: string
  title?: string
  reset?: number
  disabled?: boolean
  onChange: (value: number) => void
}) {
  const fill = ((value - min) / (max - min)) * 100
  const canReset = reset != null && reset !== value && !disabled
  return (
    <div className="field">
      <div className="field-top">
        <label htmlFor={id} title={title}>{label}</label>
        <button
          type="button"
          className={canReset ? 'value moved' : 'value'}
          title={canReset ? 'Double-click to reset' : undefined}
          tabIndex={-1}
          onDoubleClick={() => {
            if (!canReset) return
            sfx.tap()
            onChange(reset)
          }}
        >
          <span key={text}>{text}</span>
        </button>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        style={{ '--fill': `${fill}%` } as CSSProperties}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </div>
  )
}

export function Segment<T extends string | number>({
  label, options, value, disabled = false, onChange,
}: {
  label: string
  options: readonly { value: T; label: ReactNode }[]
  value: T
  disabled?: boolean
  onChange: (value: T) => void
}) {
  const pill = useId()
  return (
    <div className="segment" role="group" aria-label={label} style={{ '--n': options.length } as CSSProperties}>
      {options.map((option) => {
        const on = option.value === value
        return (
          <button
            key={String(option.value)}
            type="button"
            aria-pressed={on}
            disabled={disabled}
            onClick={() => {
              if (on) return
              sfx.tap()
              onChange(option.value)
            }}
          >
            {on && <motion.span layoutId={pill} className="segment-pill" transition={SPRING} />}
            <span className="segment-label">{option.label}</span>
          </button>
        )
      })}
    </div>
  )
}

export function Toggle({ checked, disabled = false, onChange, children }: {
  checked: boolean
  disabled?: boolean
  onChange: (next: boolean) => void
  children: ReactNode
}) {
  return (
    <label className={checked ? 'switch on' : 'switch'}>
      <input
        type="checkbox"
        className="sr"
        checked={checked}
        disabled={disabled}
        onChange={(event) => {
          sfx.tap()
          onChange(event.target.checked)
        }}
      />
      <span className="switch-track" aria-hidden="true"><span className="switch-thumb" /></span>
      {children}
    </label>
  )
}

type DropHandlers = {
  onDragOver?: (event: DragEvent<HTMLDivElement>) => void
  onDragLeave?: (event: DragEvent<HTMLDivElement>) => void
  onDrop?: (event: DragEvent<HTMLDivElement>) => void
}

export function Sheet({ open, onClose, labelledBy, drop, children }: {
  open: boolean
  onClose: () => void
  labelledBy: string
  drop?: DropHandlers
  children: ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="scrim"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={onClose}
          {...drop}
        >
          <motion.div
            className="sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby={labelledBy}
            initial={{ opacity: 0, y: 28, scale: 0.94 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 14, scale: 0.97 }}
            transition={SPRING}
            onClick={(event) => event.stopPropagation()}
          >
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

const LOVE_LINES = [
  'Free is a price. The blob respects it.',
  'The blob is blushing. A little.',
  'The blob has entered a state of love.',
  'The blob will remember this. Forever, probably.',
]

/** Pay what you want. Nothing is charged here; the choice is a kindness meter. */
export function PayModal({ open, onClose, amounts, onDownload }: {
  open: boolean
  onClose: () => void
  amounts: readonly number[]
  onDownload: () => void
}) {
  return (
    <Sheet open={open} onClose={onClose} labelledBy="nag-title">
      <PayBody amounts={amounts} onDownload={onDownload} />
    </Sheet>
  )
}

// Mounted only while the sheet is open, so each visit starts back at $0.
function PayBody({ amounts, onDownload }: { amounts: readonly number[]; onDownload: () => void }) {
  const [pick, setPick] = useState(0)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const amount = amounts[pick] ?? 0
  return (
    <>
      <div className="pay-head">
        <PayBlob love={pick} />
        <div>
          <h2 id="nag-title">Pay what you want</h2>
          <p>Sprites are hard to make, you know.</p>
        </div>
      </div>
      <Segment
        label="Price"
        options={amounts.map((value, index) => ({ value: index, label: `$${value}` }))}
        value={pick}
        onChange={setPick}
      />
      <AnimatePresence mode="wait" initial={false}>
        <motion.p
          key={pick}
          className="pay-line"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.14 }}
        >
          {LOVE_LINES[Math.min(pick, LOVE_LINES.length - 1)]}
        </motion.p>
      </AnimatePresence>
      <button
        ref={buttonRef}
        type="button"
        className="make shine"
        onClick={() => {
          celebrate(buttonRef.current, amount > 0 ? 120 : 50)
          onDownload()
        }}
      >
        <Download aria-hidden="true" /> Download now
      </button>
      <p className="fineprint">
        By downloading, you agree to the <a href="/terms" target="_blank" rel="noopener">Terms of Service</a> and <a href="/privacy" target="_blank" rel="noopener">Privacy Policy</a>.
      </p>
    </>
  )
}

export function Shortcut() {
  const mac = typeof navigator !== 'undefined' && /mac/i.test(navigator.platform)
  return <kbd className="shortcut">{mac ? '⌘' : 'Ctrl'} ↵</kbd>
}

function carriesDrop(event: globalThis.DragEvent) {
  const types = [...(event.dataTransfer?.types ?? [])]
  return types.includes('Files') || types.includes('text/uri-list')
}

/** A full-page drop target that shows up whenever a file is dragged over the window. */
export function DropVeil({ enabled, title, hint, onDrop }: {
  enabled: boolean
  title: string
  hint: string
  onDrop: (transfer: DataTransfer) => void
}) {
  const [on, setOn] = useState(false)
  const depth = useRef(0)

  useEffect(() => {
    depth.current = 0
    if (!enabled) return
    const enter = (event: globalThis.DragEvent) => {
      if (!carriesDrop(event)) return
      depth.current += 1
      setOn(true)
    }
    const leave = (event: globalThis.DragEvent) => {
      if (!carriesDrop(event)) return
      depth.current = Math.max(0, depth.current - 1)
      if (!depth.current) setOn(false)
    }
    const end = () => {
      depth.current = 0
      setOn(false)
    }
    window.addEventListener('dragenter', enter)
    window.addEventListener('dragleave', leave)
    window.addEventListener('drop', end)
    window.addEventListener('dragend', end)
    return () => {
      window.removeEventListener('dragenter', enter)
      window.removeEventListener('dragleave', leave)
      window.removeEventListener('drop', end)
      window.removeEventListener('dragend', end)
    }
  }, [enabled])

  return (
    <AnimatePresence>
      {enabled && on && (
        <motion.div
          className="veil"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onDragOver={(event) => {
            event.preventDefault()
            event.dataTransfer.dropEffect = 'copy'
          }}
          onDrop={(event) => {
            event.preventDefault()
            event.stopPropagation()
            depth.current = 0
            setOn(false)
            sfx.pop()
            onDrop(event.dataTransfer)
          }}
        >
          <motion.div
            className="veil-card"
            initial={{ scale: 0.8, y: 20 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0 }}
            transition={SPRING}
          >
            <ChompScene />
            <h2>{title}</h2>
            <p>{hint}</p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
