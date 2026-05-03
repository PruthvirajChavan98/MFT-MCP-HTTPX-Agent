import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { CopyButton } from './CopyButton'
import { collapseTokens, type TimelineBeat } from './collapseTokens'
import type { SSEEvent } from './data/sseFrames'

interface SSETimelineProps {
  caption: string
  frames: readonly SSEEvent[]
  highlightEvent?: SSEEvent['event']
  /** Visual accent for the highlight halo. Defaults to cyan. */
  accent?: 'cyan' | 'rose'
}

const EVENT_BEAD: Record<SSEEvent['event'], { fill: string; ring: string; chip: string }> = {
  trace: {
    fill: '#22d3ee',
    ring: 'rgba(34, 211, 238, 0.25)',
    chip: 'border-cyan-500/40 bg-cyan-500/10 text-cyan-200',
  },
  reasoning: {
    fill: '#a5b4fc',
    ring: 'rgba(165, 180, 252, 0.25)',
    chip: 'border-indigo-400/40 bg-indigo-400/10 text-indigo-200',
  },
  tool_call: {
    fill: '#34d399',
    ring: 'rgba(52, 211, 153, 0.25)',
    chip: 'border-emerald-400/40 bg-emerald-400/10 text-emerald-200',
  },
  token: {
    fill: '#94a3b8',
    ring: 'rgba(148, 163, 184, 0.18)',
    chip: 'border-slate-600 bg-slate-800/60 text-slate-300',
  },
  cost: {
    fill: '#fbbf24',
    ring: 'rgba(251, 191, 36, 0.25)',
    chip: 'border-amber-400/40 bg-amber-400/10 text-amber-200',
  },
  done: {
    fill: '#67e8f9',
    ring: 'rgba(103, 232, 249, 0.30)',
    chip: 'border-cyan-300/40 bg-cyan-300/10 text-cyan-100',
  },
  error: {
    fill: '#fb7185',
    ring: 'rgba(251, 113, 133, 0.30)',
    chip: 'border-rose-400/40 bg-rose-400/10 text-rose-200',
  },
}

/** Estimated cumulative milliseconds per event type — illustrative, not measured. */
const T_DELTA: Record<SSEEvent['event'], number> = {
  trace: 0,
  reasoning: 18,
  tool_call: 60,
  token: 4,
  cost: 6,
  done: 4,
  error: 2,
}

function serialize(frames: readonly SSEEvent[]): string {
  return frames.map((f) => `event: ${f.event}\ndata: ${f.data}`).join('\n\n')
}

function summarise(beat: TimelineBeat): string {
  switch (beat.event) {
    case 'trace': {
      const match = /"trace_id":"([^"]+)"/.exec(beat.data)
      if (match) {
        const id = match[1]
        return id.length > 24 ? `trace_id ${id.slice(0, 12)}…${id.slice(-6)}` : `trace_id ${id}`
      }
      return beat.data
    }
    case 'reasoning': {
      const stripped = beat.data.replace(/^"|"$/g, '')
      return stripped.length > 110 ? `${stripped.slice(0, 107)}…` : stripped
    }
    case 'tool_call': {
      const nameMatch = /"name":"([^"]+)"/.exec(beat.data)
      const outputMatch = /"output":"([^"\\]*(?:\\.[^"\\]*)*)"/.exec(beat.data)
      const name = nameMatch?.[1] ?? '?'
      const output = outputMatch?.[1].replace(/\\r\\n|\\n/g, ' ').replace(/^\s+|\s+$/g, '') ?? ''
      const trimmed = output.length > 80 ? `${output.slice(0, 77)}…` : output
      return trimmed ? `${name} → ${trimmed}` : name
    }
    case 'token':
      return beat.data
    case 'cost': {
      const total = /"total":([0-9.eE-]+)/.exec(beat.data)?.[1] ?? '?'
      const provider = /"provider":"([^"]+)"/.exec(beat.data)?.[1]
      const model = /"model":"([^"]+)"/.exec(beat.data)?.[1]
      const inTok = /"input_tokens":([0-9]+)/.exec(beat.data)?.[1]
      const outTok = /"output_tokens":([0-9]+)/.exec(beat.data)?.[1]
      const usage = inTok && outTok ? ` · ${inTok}/${outTok} tok` : ''
      const stack = [provider, model].filter(Boolean).join(' · ')
      return `$${total}${stack ? ` · ${stack}` : ''}${usage}`
    }
    case 'done': {
      const status = /"status":"([^"]+)"/.exec(beat.data)?.[1]
      return status ? `status=${status}` : beat.data
    }
    case 'error': {
      const message = /"message":"([^"]+)"/.exec(beat.data)?.[1]
      return message ?? beat.data
    }
  }
}

export function SSETimeline({ caption, frames, highlightEvent, accent = 'cyan' }: SSETimelineProps) {
  const beats = collapseTokens(frames)
  const raw = serialize(frames)

  let cumulativeMs = 0
  const ticks = beats.map((beat) => {
    cumulativeMs += T_DELTA[beat.event] * beat.count
    return cumulativeMs
  })
  const totalMs = ticks[ticks.length - 1] ?? 0

  return (
    <figure className="group relative overflow-hidden rounded-xl border border-slate-800 bg-[#070912] shadow-lg shadow-black/30">
      <header className="flex items-center justify-between border-b border-slate-800 bg-[#0c1322] px-4 py-2">
        <div className="flex items-baseline gap-3 font-mono text-[11px] tracking-[0.18em] text-slate-500">
          <span className="text-cyan-300/80">SSE</span>
          <span className="text-slate-600">/</span>
          <span className="text-slate-400">{caption}</span>
          <span className="ml-2 rounded-full border border-slate-700 px-2 py-0.5 text-[10px] uppercase tracking-wider text-slate-500">
            {frames.length} frames
          </span>
        </div>
        <CopyButton value={raw} label="Copy SSE transcript" />
      </header>

      <ol className="relative flex flex-col gap-0 px-4 py-4">
        {/* Spine */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-[28px] top-7 bottom-7 w-px bg-gradient-to-b from-slate-700 via-slate-800 to-slate-700"
        />
        {beats.map((beat, idx) => (
          <Beat
            key={beat.index}
            beat={beat}
            t={ticks[idx]}
            isLast={idx === beats.length - 1}
            highlight={highlightEvent === beat.event}
            accent={accent}
          />
        ))}
      </ol>

      <footer className="flex items-center justify-between border-t border-slate-800/80 px-4 py-2 font-mono text-[10px] text-slate-600">
        <span>
          {beats.length} beats · {frames.length} frames · ~{totalMs} ms (illustrative)
        </span>
        <span className="hidden sm:inline">ticks are estimated, not measured</span>
      </footer>

      <RawSSEDisclosure raw={raw} />
    </figure>
  )
}

interface BeatProps {
  beat: TimelineBeat
  t: number
  isLast: boolean
  highlight: boolean
  accent: 'cyan' | 'rose'
}

function Beat({ beat, t, isLast, highlight, accent }: BeatProps) {
  const palette = EVENT_BEAD[beat.event]
  const haloRing =
    accent === 'rose' ? 'ring-rose-400/40 shadow-rose-500/30' : 'ring-cyan-400/40 shadow-cyan-500/30'
  return (
    <li className={`relative grid grid-cols-[56px_1fr_auto] items-start gap-3 ${isLast ? 'pb-0' : 'pb-5'}`}>
      <div className="relative flex h-7 items-center justify-center">
        <span
          aria-hidden="true"
          className={`relative z-10 inline-block h-3 w-3 rounded-full ring-4 ${
            highlight ? `${haloRing} shadow-[0_0_18px_-2px]` : 'ring-slate-900/80'
          }`}
          style={{ backgroundColor: palette.fill, boxShadow: highlight ? `0 0 0 6px ${palette.ring}` : undefined }}
        />
      </div>
      <div className="flex flex-wrap items-baseline gap-2 pt-0.5">
        <span
          className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.16em] ${palette.chip}`}
        >
          {beat.event}
          {beat.count > 1 && <span className="text-slate-400">×{beat.count}</span>}
        </span>
        <span className="min-w-0 flex-1 break-words font-mono text-[12.5px] leading-snug text-slate-200">
          {summarise(beat)}
        </span>
      </div>
      <span className="self-center pt-0.5 font-mono text-[10px] text-slate-600">
        t≈{t} ms
      </span>
    </li>
  )
}

function RawSSEDisclosure({ raw }: { raw: string }) {
  const [open, setOpen] = useState(false)
  return (
    <details
      className="border-t border-slate-800/80 bg-slate-950/40 px-4 py-2"
      open={open}
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500 hover:text-cyan-300">
        <ChevronRight className={`h-3 w-3 transition-transform ${open ? 'rotate-90' : ''}`} />
        Show raw SSE
      </summary>
      <pre className="mt-3 overflow-x-auto font-mono text-[11.5px] leading-relaxed text-slate-300">
        {raw}
      </pre>
    </details>
  )
}
