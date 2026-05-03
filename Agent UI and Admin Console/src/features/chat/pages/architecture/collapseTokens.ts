import type { SSEEvent } from './data/sseFrames'

export interface TimelineBeat {
  /** Index of the first frame in the original stream (stable key + timing anchor). */
  index: number
  /** Number of frames merged into this beat (≥1; >1 only for `token` runs). */
  count: number
  event: SSEEvent['event']
  /** Verbatim data when count===1; concatenated short summary when folded. */
  data: string
  /** All raw frames represented by this beat (preserves fidelity for the raw <details> view). */
  frames: readonly SSEEvent[]
}

const FOLD_EVENT: SSEEvent['event'] = 'token'

/**
 * Walk frames left→right; collapse runs of consecutive `token` events into a
 * single beat. Every other event yields a 1:1 beat. Pure function — same input
 * always produces the same output.
 */
export function collapseTokens(frames: readonly SSEEvent[]): readonly TimelineBeat[] {
  const beats: TimelineBeat[] = []

  let i = 0
  while (i < frames.length) {
    const frame = frames[i]
    if (frame.event !== FOLD_EVENT) {
      beats.push({
        index: i,
        count: 1,
        event: frame.event,
        data: frame.data,
        frames: [frame],
      })
      i += 1
      continue
    }

    // Walk forward over consecutive token frames.
    const start = i
    while (i < frames.length && frames[i].event === FOLD_EVENT) {
      i += 1
    }
    const run = frames.slice(start, i)
    beats.push({
      index: start,
      count: run.length,
      event: FOLD_EVENT,
      data: foldedTokenSummary(run),
      frames: run,
    })
  }

  return beats
}

const TOKEN_SUMMARY_MAX = 80

function foldedTokenSummary(run: readonly SSEEvent[]): string {
  // Each token's `data` is a JSON-encoded chunk like `"OTP "` — strip surrounding
  // quotes when present so the folded preview reads naturally.
  const pieces = run.map((f) => stripJsonQuotes(f.data))
  const joined = pieces.join('')
  if (joined.length <= TOKEN_SUMMARY_MAX) return joined
  return `${joined.slice(0, TOKEN_SUMMARY_MAX - 1).trimEnd()}…`
}

function stripJsonQuotes(value: string): string {
  if (value.length >= 2 && value.startsWith('"') && value.endsWith('"')) {
    return value.slice(1, -1)
  }
  return value
}
