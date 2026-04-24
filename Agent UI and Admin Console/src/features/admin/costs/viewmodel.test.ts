import { describe, expect, it } from 'vitest'
import { mapSessionCostSummary } from './viewmodel'

describe('costs viewmodel', () => {
  it('sorts sessions by total cost and creates chart points with short session-id labels', () => {
    const model = mapSessionCostSummary({
      active_sessions: 2,
      total_cost: 1.2,
      total_requests: 12,
      sessions: [
        {
          session_id: 'session-bbbbbb-xyz',
          total_cost: 0.2,
          total_requests: 3,
          last_request_at: '2026-02-27T22:18:41Z',
        },
        {
          session_id: 'session-aaaaaa-xyz',
          total_cost: 1,
          total_requests: 9,
          last_request_at: '2026-02-27T22:20:00Z',
        },
      ],
    })

    expect(model.activeSessions).toBe(2)
    expect(model.totalRequests).toBe(12)
    expect(model.sessions[0].sessionId).toBe('session-aaaaaa-xyz')
    expect(model.sessions[0].conversationHref).toBe(
      '/admin/conversations?sessionId=session-aaaaaa-xyz',
    )
    // Chart labels must be the first 8 chars of the session_id with
    // dashes stripped — NOT the old `S1, S2, …` ordinals which were
    // unreadable and non-unique across refreshes.
    expect(model.series).toEqual([
      {
        name: 'sessiona',
        sessionId: 'session-aaaaaa-xyz',
        cost: 1,
        requests: 9,
      },
      {
        name: 'sessionb',
        sessionId: 'session-bbbbbb-xyz',
        cost: 0.2,
        requests: 3,
      },
    ])
  })

  it('never emits the legacy S${n} label format', () => {
    const model = mapSessionCostSummary({
      active_sessions: 3,
      total_cost: 1,
      total_requests: 30,
      sessions: Array.from({ length: 3 }, (_, i) => ({
        session_id: `sess-${i}-abcdef123456`,
        total_cost: 1 - i * 0.1,
        total_requests: 10,
        last_request_at: '2026-02-27T22:20:00Z',
      })),
    })

    for (const point of model.series) {
      expect(point.name).not.toMatch(/^S\d+$/)
      expect(point.name.length).toBeLessThanOrEqual(8)
    }
  })

  it('falls back to the raw session_id when it is shorter than 8 chars after stripping', () => {
    const model = mapSessionCostSummary({
      active_sessions: 1,
      total_cost: 1,
      total_requests: 1,
      sessions: [
        {
          session_id: 'abc',
          total_cost: 1,
          total_requests: 1,
          last_request_at: '2026-02-27T22:20:00Z',
        },
      ],
    })

    expect(model.series[0].name).toBe('abc')
  })
})
