import { describe, expect, it } from 'vitest'
import { mapSessionCostSummary } from './costs'

describe('costs viewmodel', () => {
  it('sorts sessions by total cost and creates chart points', () => {
    const model = mapSessionCostSummary({
      active_sessions: 2,
      total_cost: 1.2,
      total_requests: 12,
      sessions: [
        {
          session_id: 'session-b',
          total_cost: 0.2,
          total_requests: 3,
          last_request_at: '2026-02-27T22:18:41Z',
        },
        {
          session_id: 'session-a',
          total_cost: 1,
          total_requests: 9,
          last_request_at: '2026-02-27T22:20:00Z',
        },
      ],
    })

    expect(model.activeSessions).toBe(2)
    expect(model.totalRequests).toBe(12)
    expect(model.sessions[0].sessionId).toBe('session-a')
    expect(model.sessions[0].conversationHref).toBe('/admin/conversations?sessionId=session-a')
    expect(model.series).toEqual([
      {
        name: 'S1',
        sessionId: 'session-a',
        cost: 1,
        requests: 9,
      },
      {
        name: 'S2',
        sessionId: 'session-b',
        cost: 0.2,
        requests: 3,
      },
    ])
  })
})
