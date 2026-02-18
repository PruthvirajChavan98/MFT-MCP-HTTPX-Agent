import { type Component, For, createSignal, onMount } from 'solid-js'

interface Node {
  cx: number
  cy: number
  r: number
  fill: string
  dur: string
  delay: string
}

interface Edge {
  x1: number
  y1: number
  x2: number
  y2: number
  opacity: string
  strokeWidth: string
}

interface Signal {
  path: string
  dur: string
  delay: string
  r: string
  color: string
}

const CYAN = ['#22d3ee', '#06b6d4', '#67e8f9', '#a5f3fc', '#0891b2'] as const

const BRAIN_PATH = [
  'M 50 90',
  'C 44 90, 36 87, 30 82',
  'C 24 82, 14 76, 12 68',
  'C  6 66,  4 58,  6 50',
  'C  4 42,  8 34, 14 30',
  'C 12 22, 16 14, 24 11',
  'C 26  5, 34  2, 42  4',
  'C 44  2, 48  2, 50  3',
  'C 52  2, 56  2, 58  4',
  'C 66  2, 74  5, 76 11',
  'C 84 14, 88 22, 86 30',
  'C 92 34, 96 42, 94 50',
  'C 96 58, 94 66, 88 68',
  'C 86 76, 76 82, 70 82',
  'C 64 87, 56 90, 50 90 Z',
].join(' ')

const FOLDS: string[] = [
  'M 24 11  C 20 18, 18 28, 22 38',
  'M 12 30  C 16 38, 16 48, 14 56',
  'M 12 68  C 16 72, 20 76, 24 80',
  'M 76 11  C 80 18, 82 28, 78 38',
  'M 88 30  C 84 38, 84 48, 86 56',
  'M 88 68  C 84 72, 80 76, 76 80',
  'M 36  4  C 34 12, 32 22, 30 32',
  'M 64  4  C 66 12, 68 22, 70 32',
  'M 16 50  C 24 52, 34 50, 40 52',
  'M 84 50  C 76 52, 66 50, 60 52',
  'M 50  8  C 50 28, 50 52, 50 86',
]

const BASE_NODES = [
  { cx: 28, cy: 22 },
  { cx: 20, cy: 38 },
  { cx: 22, cy: 56 },
  { cx: 30, cy: 70 },
  { cx: 38, cy: 30 },
  { cx: 36, cy: 48 },
  { cx: 38, cy: 65 },
  { cx: 72, cy: 22 },
  { cx: 80, cy: 38 },
  { cx: 78, cy: 56 },
  { cx: 70, cy: 70 },
  { cx: 62, cy: 30 },
  { cx: 64, cy: 48 },
  { cx: 62, cy: 65 },
  { cx: 50, cy: 25 },
  { cx: 50, cy: 50 },
  { cx: 50, cy: 72 },
] as const

const BASE_EDGES: [number, number][] = [
  [0, 4],
  [4, 1],
  [1, 5],
  [5, 2],
  [2, 6],
  [6, 3],
  [0, 1],
  [4, 5],
  [5, 6],
  [7, 11],
  [11, 8],
  [8, 12],
  [12, 9],
  [9, 13],
  [13, 10],
  [7, 8],
  [11, 12],
  [12, 13],
  [0, 14],
  [14, 7],
  [4, 15],
  [15, 11],
  [2, 15],
  [15, 9],
  [6, 16],
  [16, 13],
  [4, 11],
  [5, 12],
  [1, 8],
]

const rand = (min: number, max: number) => Math.random() * (max - min) + min
const jitter = (v: number, a = 2) => +(v + rand(-a, a)).toFixed(2)
const pick = () => CYAN[Math.floor(Math.random() * CYAN.length)]
const f = (n: number) => n.toFixed(2)

function buildGraph(): { nodes: Node[]; edges: Edge[]; signals: Signal[] } {
  const nodes: Node[] = BASE_NODES.map((n) => ({
    cx: jitter(n.cx),
    cy: jitter(n.cy),
    r: +f(rand(1.8, 3.4)),
    fill: pick(),
    dur: `${f(rand(1.4, 2.6))}s`,
    delay: `-${f(rand(0, 2.5))}s`,
  }))

  const edges: Edge[] = BASE_EDGES.map(([a, b]) => ({
    x1: nodes[a].cx,
    y1: nodes[a].cy,
    x2: nodes[b].cx,
    y2: nodes[b].cy,
    opacity: f(rand(0.06, 0.22)),
    strokeWidth: f(rand(0.3, 0.8)),
  }))

  const signals: Signal[] = BASE_EDGES.map(([a, b]) => ({
    path: `M${nodes[a].cx} ${nodes[a].cy} L${nodes[b].cx} ${nodes[b].cy}`,
    dur: `${f(rand(1.6, 3.2))}s`,
    delay: `-${f(rand(0, 2.5))}s`,
    r: f(rand(0.9, 1.8)),
    color: pick(),
  }))

  return { nodes, edges, signals }
}

interface BrainIconProps {
  size?: number
}

const BrainIcon: Component<BrainIconProps> = (props) => {
  const size = () => props.size ?? 64
  const svgSize = () => size() * 0.82

  const [nodes, setNodes] = createSignal<Node[]>([])
  const [edges, setEdges] = createSignal<Edge[]>([])
  const [signals, setSignals] = createSignal<Signal[]>([])

  onMount(() => {
    const g = buildGraph()
    setNodes(g.nodes)
    setEdges(g.edges)
    setSignals(g.signals)
  })

  return (
    <>
      <style>{`
        @keyframes pulse-node {
          0%, 100% { opacity: .25; transform: scale(.65); }
          50% { opacity: 1; transform: scale(1.3); }
        }
        @keyframes travel {
          0% { offset-distance: 0%; opacity: 0; }
          8% { opacity: 1; }
          92% { opacity: 1; }
          100% { offset-distance: 100%; opacity: 0; }
        }
        @keyframes breathe {
          0%, 100% { opacity: .4; }
          50% { opacity: .9; }
        }
        .brain-node {
          animation: pulse-node var(--dur) ease-in-out infinite var(--delay);
          transform-box: fill-box;
          transform-origin: center;
        }
        .brain-signal {
          offset-rotate: 0deg;
          animation: travel var(--dur) linear infinite var(--delay);
        }
        .brain-outline { animation: breathe 3.5s ease-in-out infinite; }
        .brain-fold { animation: breathe 3.5s ease-in-out infinite .4s; }
      `}</style>

      <div
        class="flex items-center justify-center rounded-[22%] bg-zinc-900 ring-1 ring-cyan-500/10"
        style={{ width: `${size()}px`, height: `${size()}px` }}
      >
        <svg
          width={svgSize()}
          height={svgSize()}
          viewBox="0 0 100 100"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <For each={edges()}>
            {(e) => (
              <line
                x1={e.x1}
                y1={e.y1}
                x2={e.x2}
                y2={e.y2}
                stroke="#06b6d4"
                stroke-width={e.strokeWidth}
                stroke-opacity={e.opacity}
              />
            )}
          </For>

          <For each={FOLDS}>
            {(d) => (
              <path
                d={d}
                stroke="#22d3ee"
                stroke-width="0.7"
                stroke-opacity="0.2"
                stroke-linecap="round"
                fill="none"
                class="brain-fold"
              />
            )}
          </For>

          <path
            d={BRAIN_PATH}
            stroke="#22d3ee"
            stroke-width="1.6"
            stroke-linejoin="round"
            stroke-linecap="round"
            fill="rgba(6,182,212,0.04)"
            class="brain-outline"
          />

          <For each={signals()}>
            {(s) => (
              <circle
                cx={0}
                cy={0}
                r={s.r}
                fill={s.color}
                class="brain-signal"
                style={{
                  'offset-path': `path('${s.path}')`,
                  '--dur': s.dur,
                  '--delay': s.delay,
                }}
              />
            )}
          </For>

          <For each={nodes()}>
            {(n) => (
              <circle
                cx={n.cx}
                cy={n.cy}
                r={n.r}
                fill={n.fill}
                class="brain-node"
                style={{ '--dur': n.dur, '--delay': n.delay }}
              />
            )}
          </For>
        </svg>
      </div>
    </>
  )
}

export default BrainIcon
