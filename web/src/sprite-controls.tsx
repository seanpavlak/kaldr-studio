import { RangeField, Segment, Toggle } from './ui.tsx'
import { DEFAULT_RENDER, type CanvasSize, type RenderSettings, type StudioModel } from './types.ts'

const RANGES = [
  { name: 'palette_colors', label: 'Colors', min: 4, max: 24, step: 1 },
  { name: 'saturation', label: 'Saturation', min: 0.5, max: 2, step: 0.05 },
  { name: 'contrast', label: 'Contrast', min: 0.5, max: 2, step: 0.05 },
  { name: 'coverage', label: 'Coverage', min: 0.05, max: 0.8, step: 0.05, title: 'How much of a pixel must be the creature to keep it' },
  { name: 'dark_bias', label: 'Dark lines', min: 0, max: 6, step: 0.5, title: 'Extra weight for dark colors, so eyes and lines survive' },
] as const

type RangeName = (typeof RANGES)[number]['name']

const SIZES = [32, 48, 64].map((size) => ({ value: size as CanvasSize, label: size }))

function formatValue(name: RangeName, value: number) {
  if (name === 'palette_colors') return String(Math.round(value))
  if (name === 'dark_bias') return value.toFixed(1)
  return value.toFixed(2)
}

export function ModelField({ models, value, onChange }: {
  models: StudioModel[]
  value: string
  onChange: (id: string) => void
}) {
  return (
    <>
      <label htmlFor="model">Model</label>
      <div className="select">
        <select id="model" value={value} onChange={(event) => onChange(event.target.value)}>
          {models.map((item) => (
            <option key={item.id} value={item.id}>{item.label} · {item.price}</option>
          ))}
        </select>
      </div>
    </>
  )
}

/** Size, the five sliders, and the two switches. Shared by Single and Batch. */
export function SpriteFields({ render, idPrefix = '', onPatch }: {
  render: RenderSettings
  idPrefix?: string
  onPatch: (patch: Partial<RenderSettings>) => void
}) {
  return (
    <fieldset>
      <legend>Sprite</legend>
      <div className="field">
        <span className="kicker">Size</span>
        <Segment label="Size" options={SIZES} value={render.canvas} onChange={(canvas) => onPatch({ canvas })} />
      </div>
      {RANGES.map((field) => (
        <RangeField
          key={field.name}
          id={`${idPrefix}${field.name}`}
          label={field.label}
          title={'title' in field ? field.title : undefined}
          value={render[field.name]}
          min={field.min}
          max={field.max}
          step={field.step}
          reset={DEFAULT_RENDER[field.name]}
          text={formatValue(field.name, render[field.name])}
          onChange={(value) => onPatch({ [field.name]: value })}
        />
      ))}
      <div className="toggles">
        <Toggle checked={render.outline} onChange={(outline) => onPatch({ outline })}>Outline</Toggle>
        <Toggle checked={render.sticker} onChange={(sticker) => onPatch({ sticker })}>Sticker</Toggle>
      </div>
    </fieldset>
  )
}
