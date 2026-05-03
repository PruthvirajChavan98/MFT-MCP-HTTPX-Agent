import type { ReactNode } from 'react'
import { SSETimeline } from './SSETimeline'
import type { SSEEvent } from './data/sseFrames'

interface WalkthroughProps {
  index: string
  title: string
  prompt: string
  sessionId: string
  frames: readonly SSEEvent[]
  outcome: ReactNode
  variant?: 'default' | 'block'
  highlightEvent?: SSEEvent['event']
}

export function Walkthrough({
  index,
  title,
  prompt,
  sessionId,
  frames,
  outcome,
  variant = 'default',
  highlightEvent,
}: WalkthroughProps) {
  const accent =
    variant === 'block'
      ? 'border-rose-500/30 bg-rose-500/5'
      : 'border-cyan-500/20 bg-cyan-500/[0.03]'
  return (
    <article
      className={`relative overflow-hidden rounded-2xl border ${accent} shadow-lg shadow-black/30`}
    >
      <header className="flex flex-wrap items-baseline gap-3 border-b border-slate-800/80 bg-[#0c1322]/80 px-5 py-3">
        <span className="rounded-sm border border-cyan-500/30 bg-cyan-500/5 px-2 py-0.5 font-mono text-[10px] tracking-[0.22em] text-cyan-300">
          {index}
        </span>
        <h3 className="font-display text-lg font-semibold text-white">{title}</h3>
        <span className="ml-auto font-mono text-[10px] tracking-wider text-slate-500">
          session {sessionId}
        </span>
      </header>
      <div className="space-y-4 p-5">
        <div className="rounded-md border border-slate-800 bg-slate-950/40 px-4 py-3">
          <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
            user prompt
          </p>
          <p className="font-mono text-[13px] text-slate-200">"{prompt}"</p>
        </div>
        <SSETimeline
          caption={`${title} · timeline`}
          frames={frames}
          highlightEvent={highlightEvent}
          accent={variant === 'block' ? 'rose' : 'cyan'}
        />
        <div className="flex items-start gap-3 rounded-md border border-slate-800 bg-slate-950/40 px-4 py-3 text-[13px] text-slate-300">
          <span className="mt-1 inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.6)]" />
          <p className="leading-relaxed">{outcome}</p>
        </div>
      </div>
    </article>
  )
}
