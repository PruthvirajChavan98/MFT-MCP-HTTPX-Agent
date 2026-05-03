import { describe, expect, it } from 'vitest'
import { collapseTokens } from '../collapseTokens'
import type { SSEEvent } from '../data/sseFrames'

describe('collapseTokens', () => {
  it('returns an empty list for an empty stream', () => {
    expect(collapseTokens([])).toEqual([])
  })

  it('keeps a single non-token event as one beat with count=1', () => {
    const frames: readonly SSEEvent[] = [{ event: 'trace', data: '{"trace_id":"abc"}' }]
    const beats = collapseTokens(frames)
    expect(beats).toHaveLength(1)
    expect(beats[0].count).toBe(1)
    expect(beats[0].event).toBe('trace')
    expect(beats[0].data).toBe('{"trace_id":"abc"}')
    expect(beats[0].frames).toEqual(frames)
  })

  it('folds a run of consecutive token events into one beat', () => {
    const frames: readonly SSEEvent[] = [
      { event: 'token', data: '"OTP "' },
      { event: 'token', data: '"sent "' },
      { event: 'token', data: '"to "' },
      { event: 'token', data: '"9876543210."' },
    ]
    const beats = collapseTokens(frames)
    expect(beats).toHaveLength(1)
    expect(beats[0].count).toBe(4)
    expect(beats[0].event).toBe('token')
    expect(beats[0].data).toBe('OTP sent to 9876543210.')
    expect(beats[0].frames).toEqual(frames)
  })

  it('does not fold non-consecutive token runs across other events', () => {
    const frames: readonly SSEEvent[] = [
      { event: 'token', data: '"a"' },
      { event: 'reasoning', data: '"thinking"' },
      { event: 'token', data: '"b"' },
      { event: 'token', data: '"c"' },
    ]
    const beats = collapseTokens(frames)
    expect(beats.map((b) => `${b.event}×${b.count}`)).toEqual([
      'token×1',
      'reasoning×1',
      'token×2',
    ])
    expect(beats[2].data).toBe('bc')
  })

  it('truncates a very long folded token run to the summary cap', () => {
    const long = 'x'.repeat(50)
    const frames: readonly SSEEvent[] = [
      { event: 'token', data: `"${long}"` },
      { event: 'token', data: `"${long}"` },
    ]
    const beats = collapseTokens(frames)
    expect(beats).toHaveLength(1)
    expect(beats[0].count).toBe(2)
    expect(beats[0].data.endsWith('…')).toBe(true)
    expect(beats[0].data.length).toBeLessThanOrEqual(80)
  })

  it('preserves the original index for stable keys', () => {
    const frames: readonly SSEEvent[] = [
      { event: 'trace', data: '{}' },
      { event: 'token', data: '"a"' },
      { event: 'token', data: '"b"' },
      { event: 'cost', data: '{"total":0.001}' },
    ]
    const beats = collapseTokens(frames)
    expect(beats.map((b) => b.index)).toEqual([0, 1, 3])
  })
})
