import { cleanup, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (...args: unknown[]) => useQueryMock(...args),
  // queryOptions / infiniteQueryOptions are identity helpers used at module-init time in queryOptions.ts
  queryOptions: (opts: unknown) => opts,
  infiniteQueryOptions: (opts: unknown) => opts,
}))

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}))

const queryResultByKey: Record<string, unknown> = {
  'guardrail-summary': {
    total_events: 0,
    deny_events: 0,
    allow_events: 0,
    deny_rate: 0,
    avg_risk_score: 0,
  },
  'guardrail-queue': {
    depth: 0,
    oldest_age_seconds: 0,
  },
  'guardrail-judge': {
    total_evals: 0,
    avg_policy_adherence: 0,
    recent_failures: [],
  },
  'guardrail-trends': [],
  'guardrail-events': {
    items: [],
    total: 0,
    count: 0,
    offset: 0,
    limit: 25,
  },
}

function mockQueries(errors: Record<string, Error | null> = {}) {
  useQueryMock.mockImplementation(({ queryKey }: { queryKey: string[] }) => ({
    data: queryResultByKey[queryKey[0]],
    isLoading: false,
    error: errors[queryKey[0]] ?? null,
  }))
}

describe('Guardrails page states', () => {
  afterEach(() => {
    cleanup()
    useQueryMock.mockReset()
  })

  it('renders cleanly with empty data', async () => {
    mockQueries()

    const { GuardrailsPage: Guardrails } = await import('./GuardrailsPage')
    const { rerender } = render(<Guardrails />)

    expect(screen.getByText(/Guardrails Observatory/i)).toBeInTheDocument()

    rerender(<Guardrails />)

    expect(screen.getByText(/Guardrails Observatory/i)).toBeInTheDocument()
  })

  it('keeps page rendering when trends request fails', async () => {
    mockQueries({ 'guardrail-trends': new Error('Trends unavailable') })

    const { GuardrailsPage: Guardrails } = await import('./GuardrailsPage')
    render(<Guardrails />)

    expect(screen.getByText(/Guardrails Observatory/i)).toBeInTheDocument()
    expect(screen.getByText(/Trend data unavailable: Trends unavailable/i)).toBeInTheDocument()
    expect(screen.getByText(/No events/i)).toBeInTheDocument()
  })

  it('shows inline events error without collapsing trend and summary panels', async () => {
    mockQueries({ 'guardrail-events': new Error('Events unavailable') })

    const { GuardrailsPage: Guardrails } = await import('./GuardrailsPage')
    render(<Guardrails />)

    expect(screen.getByText(/Guardrails Observatory/i)).toBeInTheDocument()
    expect(screen.getByText(/Events unavailable/i)).toBeInTheDocument()
    expect(screen.getByText(/No trend data available./i)).toBeInTheDocument()
  })

  it('allows a row to be expanded and persists the expansion across sort order changes', async () => {
    // Regression test for the bug where buildEventKey included the array index,
    // so sorting (or refetching after a filter change) gave the expanded key a
    // new position, the lookup memo failed, and a cleanup effect reset the
    // expansion to null. Fix: drop index from the key.
    const events = [
      {
        trace_id: 'trace-a',
        event_time: '2026-04-17T12:00:01.123456Z',
        session_id: 'session-a',
        risk_score: 0.9,
        risk_decision: 'block',
        request_path: '/agent/stream',
        reasons: ['policy violation'],
      },
      {
        trace_id: 'trace-b',
        event_time: '2026-04-17T12:00:02.123456Z',
        session_id: 'session-b',
        risk_score: 0.2,
        risk_decision: 'allow',
        request_path: '/agent/stream',
        reasons: ['clean'],
      },
    ]
    useQueryMock.mockImplementation(({ queryKey }: { queryKey: string[] }) => {
      if (queryKey[0] === 'guardrail-events') {
        return {
          data: { items: events, total: events.length, count: events.length, offset: 0, limit: 25 },
          isLoading: false,
          error: null,
        }
      }
      return {
        data: queryResultByKey[queryKey[0]],
        isLoading: false,
        error: null,
      }
    })

    const { GuardrailsPage: Guardrails } = await import('./GuardrailsPage')
    render(
      <MemoryRouter>
        <Guardrails />
      </MemoryRouter>,
    )

    // Two rows means two expand buttons present
    const expandButtons = screen.getAllByLabelText(/expand row/i)
    expect(expandButtons.length).toBe(2)

    // Click the second row's expand button. Before the fix this would flash
    // open and then auto-collapse because the memo's events.find() used a
    // different index than sortedEvents.map().
    const { fireEvent } = await import('@testing-library/react')
    fireEvent.click(expandButtons[1])

    // After click, exactly one row should be in the expanded state.
    const collapseButtons = await screen.findAllByLabelText(/collapse row/i)
    expect(collapseButtons.length).toBe(1)

    // Trigger a sort change by clicking the "time" column header (the sort
    // it toggles between asc/desc — index of the expanded event may shift
    // inside `events` but the key is now index-free so expansion survives).
    const timeHeader = screen.getByText(/^time$/i)
    fireEvent.click(timeHeader)

    // Expansion must persist across the sort direction change.
    const stillCollapsible = screen.getAllByLabelText(/collapse row/i)
    expect(stillCollapsible.length).toBe(1)
  })
})
