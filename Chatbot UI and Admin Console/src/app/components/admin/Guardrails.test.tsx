import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

const useQueryMock = vi.fn()
const useAdminContextMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (...args: unknown[]) => useQueryMock(...args),
}))

vi.mock('./AdminContext', () => ({
  useAdminContext: () => useAdminContextMock(),
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
    useAdminContextMock.mockReset()
  })

  it('shows admin key requirement when key is missing', async () => {
    mockQueries()
    useAdminContextMock.mockReturnValue({
      adminKey: '',
      setAdminKey: vi.fn(),
      openrouterKey: '',
      setOpenrouterKey: vi.fn(),
      groqKey: '',
      setGroqKey: vi.fn(),
    })

    const { Guardrails } = await import('./Guardrails')
    render(<Guardrails />)

    expect(screen.getByText(/Set X-Admin-Key to view guardrail events/i)).toBeInTheDocument()
  })

  it('does not crash when auth state changes across rerenders', async () => {
    mockQueries()

    const adminContextValues = [
      {
        adminKey: '',
        setAdminKey: vi.fn(),
        openrouterKey: '',
        setOpenrouterKey: vi.fn(),
        groqKey: '',
        setGroqKey: vi.fn(),
      },
      {
        adminKey: 'admin-key',
        setAdminKey: vi.fn(),
        openrouterKey: '',
        setOpenrouterKey: vi.fn(),
        groqKey: '',
        setGroqKey: vi.fn(),
      },
    ]

    let idx = 0
    useAdminContextMock.mockImplementation(() => {
      const value = adminContextValues[Math.min(idx, adminContextValues.length - 1)]
      idx += 1
      return value
    })

    const { Guardrails } = await import('./Guardrails')
    const { rerender } = render(<Guardrails />)

    expect(screen.getAllByText(/Set X-Admin-Key to view guardrail events/i).length).toBeGreaterThan(0)

    rerender(<Guardrails />)

    expect(screen.getByText(/Guardrails Observatory/i)).toBeInTheDocument()
  })

  it('keeps page rendering when trends request fails', async () => {
    mockQueries({ 'guardrail-trends': new Error('Trends unavailable') })
    useAdminContextMock.mockReturnValue({
      adminKey: 'admin-key',
      setAdminKey: vi.fn(),
      openrouterKey: '',
      setOpenrouterKey: vi.fn(),
      groqKey: '',
      setGroqKey: vi.fn(),
    })

    const { Guardrails } = await import('./Guardrails')
    render(<Guardrails />)

    expect(screen.getByText(/Guardrails Observatory/i)).toBeInTheDocument()
    expect(screen.getByText(/Trend data unavailable: Trends unavailable/i)).toBeInTheDocument()
    expect(screen.getByText(/No events/i)).toBeInTheDocument()
  })

  it('shows inline events error without collapsing trend and summary panels', async () => {
    mockQueries({ 'guardrail-events': new Error('Events unavailable') })
    useAdminContextMock.mockReturnValue({
      adminKey: 'admin-key',
      setAdminKey: vi.fn(),
      openrouterKey: '',
      setOpenrouterKey: vi.fn(),
      groqKey: '',
      setGroqKey: vi.fn(),
    })

    const { Guardrails } = await import('./Guardrails')
    render(<Guardrails />)

    expect(screen.getByText(/Guardrails Observatory/i)).toBeInTheDocument()
    expect(screen.getByText(/Events unavailable/i)).toBeInTheDocument()
    expect(screen.getByText(/No trend data available./i)).toBeInTheDocument()
  })
})
