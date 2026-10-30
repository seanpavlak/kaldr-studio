import type { ReactNode } from 'react'

// Hand-drawn pixel art for the empty states. Each map is one string per row;
// a character picks a color from the palette and '.' is transparent.

export type Palette = Record<string, string>

const BASE: Palette = {
  k: '#1a1410',
  w: '#f4f0e8',
  g: '#8f877c',
  G: '#5c554c',
  p: '#ef7a8a',
  a: '#e4a15a',
  A: '#f6c98a',
  d: '#b06e32',
  c: '#1f1c18',
  C: '#2a2620',
  y: '#f5c542',
  Y: '#c08a1e',
  b: '#c9925a',
  B: '#8a5a2b',
  r: '#e36a4f',
}

const TINTS = {
  amber: {},
  teal: { a: '#6fd3c1', A: '#b4f0e4', d: '#3c9b8c' },
  violet: { a: '#a78bfa', A: '#d4c6ff', d: '#6d55c9' },
  rose: { a: '#f08aa0', A: '#ffc4d0', d: '#b8536b' },
} satisfies Record<string, Palette>

export type Tint = keyof typeof TINTS

function runs(map: readonly string[]) {
  const out: { x: number; y: number; w: number; ch: string }[] = []
  map.forEach((row, y) => {
    let x = 0
    while (x < row.length) {
      const ch = row[x]
      let end = x + 1
      while (end < row.length && row[end] === ch) end += 1
      if (ch !== '.' && ch !== ' ') out.push({ x, y, w: end - x, ch })
      x = end
    }
  })
  return out
}

export function Px({ map, x = 0, y = 0, palette, className }: {
  map: readonly string[]
  x?: number
  y?: number
  palette?: Palette
  className?: string
}) {
  const colors = { ...BASE, ...palette }
  // The class sits on an outer group so CSS animations never fight the translate.
  return (
    <g className={className}>
      <g transform={`translate(${x} ${y})`}>
        {runs(map).map((run) => (
          <rect key={`${run.x}-${run.y}`} x={run.x} y={run.y} width={run.w} height={1} fill={colors[run.ch] ?? '#f0f'} />
        ))}
      </g>
    </g>
  )
}

function Art({ w, h, scale = 6, label, className, children }: {
  w: number
  h: number
  scale?: number
  label: string
  className?: string
  children: ReactNode
}) {
  return (
    <svg
      className={className ? `pixel-art ${className}` : 'pixel-art'}
      viewBox={`0 0 ${w} ${h}`}
      width={w * scale}
      height={h * scale}
      role="img"
      aria-label={label}
      shapeRendering="crispEdges"
    >
      {children}
    </svg>
  )
}

const BLOB = [
  '.....kkkkkk.....',
  '...kkaaaaaakk...',
  '..kaaAAaaaaaak..',
  '.kaaAAaaaaaaaak.',
  '.kaAaaaaaaaaaak.',
  'kaaaaaaaaaaaaaak',
  'kaaaaaaaaaaaaaak',
  'kaaaaaaaaaaaaaak',
  'kaapaaaaaaaapaak',
  'kdaaaaaaaaaaaadk',
  'kddaaaaaaaaaaddk',
  '.kddddddddddddk.',
  '..kkkkkkkkkkkk..',
]

const BLOB_EYES = [
  '', '', '', '', '',
  '....wk....wk....',
  '....kk....kk....',
]

const BLOB_ASLEEP = [
  '', '', '', '', '', '',
  '....kk....kk....',
]

const BLOB_HEARTS = [
  '', '', '', '',
  '...r.r....r.r...',
  '...rrr....rrr...',
  '....r......r....',
]

const BLOB_SMILE = [
  '', '', '', '', '', '', '', '',
  '.......kk.......',
]

const BLOB_GRIN = [
  '', '', '', '', '', '', '', '',
  '......k..k......',
  '.......kk.......',
]

const BLOB_MOUTH = [
  '', '', '', '', '', '', '', '',
  '......kkkk......',
  '......kppk......',
  '......kkkk......',
]

export function Blob({ tint = 'amber', mood = 'smile', x = 0, y = 0, className }: {
  tint?: Tint
  mood?: 'smile' | 'grin' | 'chomp' | 'hearts' | 'asleep'
  x?: number
  y?: number
  className?: string
}) {
  const palette = TINTS[tint]
  return (
    <g className={className ? `blob ${className}` : 'blob'}>
      <g transform={`translate(${x} ${y})`}>
      <Px map={BLOB} palette={palette} />
      {mood === 'hearts' && <Px map={BLOB_HEARTS} className="hearts" />}
      {mood === 'asleep' && <Px map={BLOB_ASLEEP} />}
      {mood !== 'hearts' && mood !== 'asleep' && <Px map={BLOB_EYES} className="eyes" />}
      {mood === 'chomp' && <Px map={BLOB_MOUTH} className="mouth" />}
      {mood === 'grin' && <Px map={BLOB_GRIN} />}
      {(mood === 'smile' || mood === 'hearts' || mood === 'asleep') && <Px map={BLOB_SMILE} />}
      </g>
    </g>
  )
}

function frameMap(size: number) {
  return Array.from({ length: size }, (_, y) => Array.from({ length: size }, (_, x) => {
    const edge = Math.min(x, y, size - 1 - x, size - 1 - y)
    if (edge === 0) return 'k'
    if (edge === 1) return x + y < size ? 'A' : 'd'
    if (edge === 2) return 'a'
    if (edge === 3) return 'k'
    return (Math.floor(x / 2) + Math.floor(y / 2)) % 2 ? 'C' : 'c'
  }).join(''))
}

const FRAME = frameMap(22)

const QUESTION = [
  '.AAA.',
  'A...A',
  '....A',
  '..AA.',
  '..A..',
  '.....',
  '..A..',
]

/** An empty frame, and a blob hoping you will fill it. */
export function FrameScene() {
  return (
    <Art w={40} h={30} label="A blob waiting beside an empty frame">
      <Px map={FRAME} x={2} y={4} className="frame-tilt" />
      <Px map={QUESTION} x={31} y={1} className="float" />
      <g className="hop"><Blob x={23} y={16} /></g>
    </Art>
  )
}

/** Three blobs in a line. None of them brought anything. */
export function CongaScene() {
  return (
    <Art w={58} h={22} label="Three blobs in a line">
      <g className="hop"><Blob x={2} y={7} tint="teal" /></g>
      <g className="hop d1"><Blob x={21} y={7} tint="amber" mood="grin" /></g>
      <g className="hop d2"><Blob x={40} y={7} tint="violet" /></g>
    </Art>
  )
}

const CASSETTE = [
  'kkkkkkkkkkkkkkkkkk',
  'kggggggggggggggggk',
  'kgwwwwwwwwwwwwwwgk',
  'kgwaaaaaaaaaaaawgk',
  'kgwwwwwwwwwwwwwwgk',
  'kggkkkkggggkkkkggk',
  'kggkwwkggggkwwkggk',
  'kggkkkkggggkkkkggk',
  'kggggggggggggggggk',
  'kgggkkkkkkkkkkgggk',
  'kggkGGGGGGGGGGkggk',
  'kkkkkkkkkkkkkkkkkk',
]

const CASSETTE_SHUT = [
  '', '', '', '', '', '',
  '....kk......kk....',
]

const CASSETTE_OPEN = [
  '', '', '', '', '', '',
  '....kw......kw....',
]

const ZED = [
  'gggg',
  '..g.',
  '.g..',
  'gggg',
]

function Cassette({ x = 0, y = 0, tint = 'amber', className }: { x?: number; y?: number; tint?: Tint; className?: string }) {
  return (
    <g className={className ? `cassette ${className}` : 'cassette'}>
      <g transform={`translate(${x} ${y})`}>
        <Px map={CASSETTE} palette={TINTS[tint]} />
        <Px map={CASSETTE_SHUT} className="shut" />
        <Px map={CASSETTE_OPEN} className="open" />
      </g>
    </g>
  )
}

/** A tape, asleep. */
export function TapeScene() {
  return (
    <Art w={36} h={26} label="A sleeping cassette tape">
      <g className="breathe"><Cassette x={4} y={12} /></g>
      <Px map={ZED} x={24} y={6} className="zed" />
      <Px map={ZED} x={28} y={2} className="zed d1" />
      <Px map={ZED} x={32} y={-2} className="zed d2" />
    </Art>
  )
}

/** A whole shelf of tapes, all asleep. */
export function ShelfScene() {
  return (
    <Art w={64} h={24} label="Three sleeping cassette tapes">
      <g className="breathe"><Cassette x={1} y={10} tint="teal" /></g>
      <g className="breathe d1"><Cassette x={23} y={10} /></g>
      <g className="breathe d2"><Cassette x={45} y={10} tint="violet" /></g>
      <Px map={ZED} x={38} y={2} className="zed" />
      <Px map={ZED} x={58} y={1} className="zed d1" />
    </Art>
  )
}

const BUBBLE = [
  '..kkkkkkkkkkkkkk..',
  '.kwwwwwwwwwwwwwwk.',
  'kwwwwwwwwwwwwwwwwk',
  'kwwwwwwwwwwwwwwwwk',
  'kwwwwwwwwwwwwwwwwk',
  'kwwwwwwwwwwwwwwwwk',
  'kwwwwwwwwwwwwwwwwk',
  'kwwwwwwwwwwwwwwwwk',
  '.kwwwwwwwwwwwwwwk.',
  '..kkkkwwkkkkkkkk..',
  '.....kwk..........',
  '....kk............',
]

const DOT = ['aa', 'aa']

/** A blob, mid-sentence. */
export function BubbleScene({ talking = true }: { talking?: boolean }) {
  return (
    <Art w={38} h={30} label="A blob with a speech bubble" className={talking ? 'talking' : 'hushed'}>
      <g className="float slow">
        <Px map={BUBBLE} x={16} y={1} />
        <Px map={DOT} x={20} y={5} className="dot" />
        <Px map={DOT} x={24} y={5} className="dot d1" />
        <Px map={DOT} x={28} y={5} className="dot d2" />
      </g>
      <g className="hop"><Blob x={2} y={16} mood={talking ? 'chomp' : 'smile'} /></g>
    </Art>
  )
}

const CRATE = [
  '.....kkkkkk.....',
  '....kyyyyyyk....',
  '...kyyYyyyyyk...',
  '...kyyYyyyyyk...',
  '.kkkkkkkkkkkkkk.',
  '.kYYYYYYYYYYYYk.',
  'kkkkkkkkkkkkkkkk',
  'kbbbbbbbbbbbbbbk',
  'kbBbbbbbbbbbbBbk',
  'kbbbbbbbbbbbbbbk',
  'kBBBBBBBBBBBBBBk',
  'kbbbbbbbbbbbbbbk',
  'kbBbbbbkkbbbbBbk',
  'kbbbbbbbbbbbbbbk',
  'kkkkkkkkkkkkkkkk',
]

const CRATE_EYES = [
  '', '', '', '', '', '', '', '',
  '.....w....w.....',
  '.....k....k.....',
]

const CONE = [
  '...k...',
  '..kak..',
  '..kwk..',
  '.kaaak.',
  '.kwwwk.',
  'kaaaaak',
  'kkkkkkk',
]

/** A box in a hard hat. It is very flat. */
export function CrateScene() {
  return (
    <Art w={36} h={24} label="A crate wearing a hard hat">
      <Px map={CONE} x={1} y={16} />
      <g className="wobble">
        <Px map={CRATE} x={10} y={8} />
        <Px map={CRATE_EYES} x={10} y={8} className="eyes" />
      </g>
      <Px map={CONE} x={28} y={16} />
    </Art>
  )
}

/** The blob, mouth open, for when something is dragged over the page. */
export function ChompScene() {
  return (
    <Art w={16} h={13} scale={10} label="A hungry blob">
      <Blob mood="chomp" className="chomping" />
    </Art>
  )
}

export function PayBlob({ love }: { love: number }) {
  return (
    <Art w={16} h={13} scale={5} label="A blob" className={`love-${love}`}>
      <g className="hop"><Blob mood={love >= 2 ? 'hearts' : love === 1 ? 'grin' : 'smile'} /></g>
    </Art>
  )
}

const ZED_SMALL = [
  'ggg',
  '.g.',
  'ggg',
]

/** Blobert, asleep in line until it is his turn. */
export function NapScene() {
  return (
    <Art w={24} h={20} scale={2.5} label="Blobert, asleep">
      <g className="breathe"><Blob x={2} y={6} mood="asleep" /></g>
      <Px map={ZED_SMALL} x={17} y={3} className="zed" />
      <Px map={ZED_SMALL} x={20} y={0} className="zed d1" />
    </Art>
  )
}

const DIGITS: Record<string, string[]> = {
  '4': ['k.k', 'k.k', 'kkk', '..k', '..k'],
  '0': ['kkk', 'k.k', 'k.k', 'k.k', 'kkk'],
}

function signMap(text: string) {
  const glyphs = [...text].map((ch) => DIGITS[ch])
  const inner = glyphs.length * 4 - 1
  const edge = 'k'.repeat(inner + 4)
  const blank = `k${'b'.repeat(inner + 2)}k`
  const rows = DIGITS['0'].map((_, y) => `kb${glyphs.map((glyph) => glyph[y].replaceAll('.', 'b')).join('b')}bk`)
  const mid = Math.floor((inner + 4) / 2)
  const post = `${'.'.repeat(mid - 1)}kBk${'.'.repeat(inner + 4 - mid - 2)}`
  return [edge, blank, ...rows, blank, edge, ...Array(11).fill(post)]
}

const SIGN = signMap('404')

/** Blobert, next to a signpost, with no idea where he is. */
export function LostScene() {
  return (
    <Art w={40} h={26} label="Blobert, lost beside a 404 signpost">
      <g className="wobble"><Px map={SIGN} x={2} y={4} /></g>
      <Px map={QUESTION} x={33} y={2} className="float" />
      <g className="hop"><Blob x={21} y={13} /></g>
    </Art>
  )
}

export function Logo() {
  return (
    <svg className="logo" viewBox="0 0 16 13" width={22} height={18} aria-hidden="true" shapeRendering="crispEdges">
      <Blob />
    </svg>
  )
}
