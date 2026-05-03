import { SSETimeline } from './SSETimeline'
import type { SSEEvent } from './data/sseFrames'

interface GuardComparisonProps {
  happyFrames: readonly SSEEvent[]
  blockedFrames: readonly SSEEvent[]
  happyHighlight?: SSEEvent['event']
  blockedHighlight?: SSEEvent['event']
}

export function GuardComparison({
  happyFrames,
  blockedFrames,
  happyHighlight = 'tool_call',
  blockedHighlight = 'error',
}: GuardComparisonProps) {
  return (
    <div className="relative">
      {/* Divergence baseline — visual pun: identical at t=0, then split */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-6 top-[120px] hidden h-px bg-gradient-to-r from-transparent via-cyan-500/20 to-transparent lg:block"
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Rail tone="emerald" label="HAPPY PATH · pass">
          <SSETimeline
            caption="natural login phrasing"
            frames={happyFrames}
            highlightEvent={happyHighlight}
            accent="cyan"
          />
        </Rail>
        <Rail tone="rose" label="BLOCKED · decision=block">
          <SSETimeline
            caption="literal command-style prompt"
            frames={blockedFrames}
            highlightEvent={blockedHighlight}
            accent="rose"
          />
        </Rail>
      </div>
      <p className="mt-3 max-w-2xl font-mono text-[10.5px] leading-relaxed text-slate-500">
        Both streams emit a <span className="text-cyan-300">trace</span> at t=0. The happy path
        continues into <span className="text-indigo-300">reasoning → tool_call → token → cost →
        done</span>; the blocked path emits an <span className="text-rose-300">error</span> instead
        and closes. Visually identical opening, divergent payloads — the diagnostic frame is the
        second beat.
      </p>
    </div>
  )
}

interface RailProps {
  tone: 'emerald' | 'rose'
  label: string
  children: React.ReactNode
}

function Rail({ tone, label, children }: RailProps) {
  const eyebrow =
    tone === 'rose'
      ? 'text-rose-300 border-rose-500/30 bg-rose-500/5'
      : 'text-emerald-300 border-emerald-500/30 bg-emerald-500/5'
  return (
    <div>
      <p
        className={`mb-3 inline-flex items-center gap-2 rounded-sm border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.22em] ${eyebrow}`}
      >
        {label}
      </p>
      {children}
    </div>
  )
}
