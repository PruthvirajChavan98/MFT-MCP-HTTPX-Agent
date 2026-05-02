import { CopyButton } from './CopyButton'
import type { SSEEvent } from './data/sseFrames'

interface SSEFrameProps {
  caption: string
  frames: readonly SSEEvent[]
  highlightEvent?: SSEEvent['event']
}

const EVENT_COLOR: Record<SSEEvent['event'], string> = {
  trace: 'text-slate-400',
  reasoning: 'text-indigo-300',
  tool_call: 'text-emerald-300',
  token: 'text-slate-500',
  cost: 'text-amber-300',
  done: 'text-cyan-300',
  error: 'text-rose-300',
}

function serialize(frames: readonly SSEEvent[]): string {
  return frames.map((f) => `event: ${f.event}\ndata: ${f.data}`).join('\n\n')
}

export function SSEFrame({ caption, frames, highlightEvent }: SSEFrameProps) {
  const raw = serialize(frames)
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
      <div className="overflow-x-auto px-4 py-4 font-mono text-[12.5px] leading-relaxed">
        {frames.map((frame, idx) => {
          const isHighlight = highlightEvent && frame.event === highlightEvent
          return (
            <div
              key={idx}
              className={`${idx > 0 ? 'mt-3' : ''} ${
                isHighlight ? 'rounded-md bg-cyan-500/5 px-2 py-1 ring-1 ring-cyan-500/20' : ''
              }`}
            >
              <div className="flex items-baseline gap-2">
                <span className="select-none text-slate-600">event:</span>
                <span className={`font-semibold ${EVENT_COLOR[frame.event]}`}>{frame.event}</span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="select-none text-slate-600">data:</span>
                <span className="break-all text-slate-200">{frame.data}</span>
              </div>
            </div>
          )
        })}
      </div>
    </figure>
  )
}
