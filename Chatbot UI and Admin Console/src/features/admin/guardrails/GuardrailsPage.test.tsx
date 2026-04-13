import { cleanup, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
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
})
