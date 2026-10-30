export type CanvasSize = 32 | 48 | 64

export type RenderSettings = {
  canvas: CanvasSize
  palette_colors: number
  saturation: number
  contrast: number
  coverage: number
  dark_bias: number
  outline: boolean
  sticker: boolean
}

export type JobFiles = {
  reference?: string
  stylized?: string
  final?: string
  idle?: string
  idle_json?: string
  gif?: string
}

export type StudioModel = {
  id: string
  label: string
  price: string
  usd: number
  estimate: boolean
}

export type BatchItem = {
  job_id: string
  name: string
  job: Job | null
}

export type Batch = {
  id: string
  model: string
  render: RenderSettings
  items: BatchItem[]
}

export type Job = {
  id: string
  url: string
  status: 'running' | 'done' | 'error'
  stage: string
  error: string | null
  model?: string | null
  render: RenderSettings | null
  files: JobFiles
}

export const FALLBACK_MODEL: StudioModel = {
  id: 'black-forest-labs/flux.2-klein-4b',
  label: 'FLUX.2 Klein 4B',
  price: '$0.014',
  usd: 0.014,
  estimate: false,
}

export type IdleMeta = {
  frames: number
  frame_ms: number[]
}

export const DEFAULT_RENDER: RenderSettings = {
  canvas: 48,
  palette_colors: 14,
  saturation: 1.25,
  contrast: 1.1,
  coverage: 0.35,
  dark_bias: 3,
  outline: true,
  sticker: false,
}
