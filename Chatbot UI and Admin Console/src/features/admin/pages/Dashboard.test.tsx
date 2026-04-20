import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Dashboard } from './Dashboard'

/**
 * The Dashboard renders lazily-loaded recharts components; mock them out
 * so we can assert on the granularity-tabs wiring without paying the
 * recharts cost in tests. We capture the `activityTrend` prop the child
 * receives so we can assert on the bucket reshape when granularity flips.
 */
const capturedCharts: { activityTrend?: unknown[]; volumeGranularity?: string }[] = []
vi.mock('./DashboardCharts', () => ({
  default: (props: {
    activityTrend: unknown[]
    volumeGranularity: string
    onVolumeGranularityChange: (g: string) => void
  }) => {
    capturedCharts.push({
      activityTrend: props.activityTrend,
      volumeGranularity: props.volumeGranularity,
    })
    return (
      <div data-testid="charts-stub">
        <span data-testid="point-count">{props.activityTrend.length}</span>
        <span data-testid="active-granularity">{props.volumeGranularity}</span>
        <button
          type="button"
          data-testid="flip-weekly"
          onClick={() => props.onVolumeGranularityChange('week')}
        >
          flip
        </button>
      </div>
    )
  },
}))

// The admin API fetches are mocked globally so Dashboard's useQuery calls
// resolve without the network. We return 40 daily traces to ensure the
// bucket math has enough data to produce distinct Daily / Weekly counts.
const FORTY_DAILY_TRACES = Array.from({ length: 40 }, (_, i) => {
  const d = new Date(Date.UTC(2026, 2, 1))
  d.setUTCDate(d.getUTCDate() + i) // 2026-03-01 .. 2026-04-09
  return {
    trace_id: `t-${i}`,
    session_id: `s-${i}`,
    status: 'success',
    model: 'openai/gpt-oss-120b',
    latency_ms: 100,
    started_at: d.toISOString(),
  }
})

vi.mock('@features/admin/api/admin', () => ({
  fetchEvalTraces: vi.fn(async () => FORTY_DAILY_TRACES),
  fetchSessionCostSummary: vi.fn(async () => ({
    active_sessions: 0,
    total_cost: 0,
    total_requests: 0,
    sessions: [],
  })),
  fetchQuestionTypes: vi.fn(async () => []),
  fetchGuardrailEvents: vi.fn(async () => ({
    items: [],
    count: 0,
    total: 0,
    offset: 0,
    limit: 0,
  })),
}))

function renderDashboard() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
  })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  window.localStorage.clear()
  capturedCharts.length = 0
})

afterEach(() => {
  cleanup()
})

describe('Dashboard — Request Volume granularity', () => {
  it('buckets 40 distinct days into ~40 daily points by default', async () => {
    renderDashboard()
    await waitFor(() => {
      expect(screen.getByTestId('active-granularity')).toHaveTextContent('day')
    })
    // 40 distinct UTC days → 40 bucket points (no gap fill needed).
    await waitFor(() => {
      expect(screen.getByTestId('point-count')).toHaveTextContent('40')
    })
  })

  it('re-buckets the same data into weekly points when granularity flips', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.getByTestId('active-granularity')).toHaveTextContent('day'))

    fireEvent.click(screen.getByTestId('flip-weekly'))

    await waitFor(() =>
      expect(screen.getByTestId('active-granularity')).toHaveTextContent('week'),
    )
    // 40 days span ~6 ISO weeks (2026-W09 .. 2026-W15 → 7 weeks inclusive).
    // Assert materially fewer points than the daily bucket (sanity check
    // that rebucketing actually happened).
    const count = Number(screen.getByTestId('point-count').textContent)
    expect(count).toBeGreaterThan(5)
    expect(count).toBeLessThanOrEqual(7)
  })

  it('persists the chosen granularity to localStorage for returning visits', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.getByTestId('active-granularity')).toHaveTextContent('day'))

    fireEvent.click(screen.getByTestId('flip-weekly'))
    await waitFor(() =>
      expect(screen.getByTestId('active-granularity')).toHaveTextContent('week'),
    )

    expect(
      window.localStorage.getItem('mft_admin_granularity_request-volume_v1'),
    ).toBe('week')
  })
})
