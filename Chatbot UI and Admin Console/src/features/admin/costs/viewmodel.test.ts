import { describe, expect, it } from 'vitest'
import { mapCostOverTime, mapSessionCostSummary } from './viewmodel'

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

describe('mapCostOverTime', () => {
  it('returns an empty series when there are no sessions', () => {
    expect(mapCostOverTime(undefined, 'day')).toEqual([])
    expect(
      mapCostOverTime(
        {
          active_sessions: 0,
          total_cost: 0,
          total_requests: 0,
          sessions: [],
        },
        'week',
      ),
    ).toEqual([])
  })

  it('sums total_cost per day bucket keyed by last_request_at', () => {
    const points = mapCostOverTime(
      {
        active_sessions: 3,
        total_cost: 0.3,
        total_requests: 9,
        sessions: [
          {
            session_id: 'a',
            total_cost: 0.05,
            total_requests: 3,
            last_request_at: '2026-04-04T10:00:00Z',
          },
          {
            session_id: 'b',
            total_cost: 0.07,
            total_requests: 2,
            last_request_at: '2026-04-04T23:00:00Z',
          },
          {
            session_id: 'c',
            total_cost: 0.18,
            total_requests: 4,
            last_request_at: '2026-04-05T08:00:00Z',
          },
        ],
      },
      'day',
    )

    expect(points.map((p) => p.bucket)).toEqual(['2026-04-04', '2026-04-05'])
    expect(points[0].cost).toBeCloseTo(0.12, 6)
    expect(points[1].cost).toBeCloseTo(0.18, 6)
    expect(points[0].label).toBe('Apr 4')
  })

  it('collapses multiple days into one bucket at weekly granularity', () => {
    const points = mapCostOverTime(
      {
        active_sessions: 2,
        total_cost: 0.2,
        total_requests: 5,
        sessions: [
          {
            session_id: 'monday',
            total_cost: 0.1,
            total_requests: 2,
            last_request_at: '2026-03-30T10:00:00Z', // Mon of week A
          },
          {
            session_id: 'sunday',
            total_cost: 0.1,
            total_requests: 3,
            last_request_at: '2026-04-05T22:00:00Z', // Sun of week A
          },
        ],
      },
      'week',
    )

    expect(points).toHaveLength(1)
    expect(points[0].bucket).toBe('2026-03-30')
    expect(points[0].cost).toBeCloseTo(0.2, 6)
  })

  it('skips sessions whose last_request_at is missing', () => {
    const points = mapCostOverTime(
      {
        active_sessions: 2,
        total_cost: 0.15,
        total_requests: 5,
        sessions: [
          {
            session_id: 'a',
            total_cost: 0.1,
            total_requests: 3,
            last_request_at: '2026-04-04T10:00:00Z',
          },
          {
            session_id: 'orphan',
            total_cost: 0.05,
            total_requests: 2,
            last_request_at: '',
          },
        ],
      },
      'day',
    )

    expect(points).toHaveLength(1)
    expect(points[0].cost).toBeCloseTo(0.1, 6)
  })
})
