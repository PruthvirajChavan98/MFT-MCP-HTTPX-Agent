import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Dashboard } from './Dashboard'
import type { GuardrailEvent } from '@features/admin/api/guardrails'

// Regression guard: Dashboard's "Guardrail Blocks" stat card once filtered by
// `risk_decision === 'deny'`, but backend vocabulary is
// {block, allow, degraded_allow} — never 'deny'. The card silently reported
// zero despite real blocks in the DB. The fix routes the filter through
// `isBlockingDecision`, and this test locks that down.

const {
  fetchEvalTracesMock,
  fetchGuardrailEventsMock,
  fetchQuestionTypesMock,
  fetchSessionCostSummaryMock,
} = vi.hoisted(() => ({
  fetchEvalTracesMock: vi.fn(),
  fetchGuardrailEventsMock: vi.fn(),
  fetchQuestionTypesMock: vi.fn(),
  fetchSessionCostSummaryMock: vi.fn(),
}))

vi.mock('@features/admin/api/admin', () => ({
  fetchEvalTraces: (...args: unknown[]) => fetchEvalTracesMock(...args),
  fetchGuardrailEvents: (...args: unknown[]) => fetchGuardrailEventsMock(...args),
  fetchQuestionTypes: (...args: unknown[]) => fetchQuestionTypesMock(...args),
  fetchSessionCostSummary: (...args: unknown[]) => fetchSessionCostSummaryMock(...args),
}))

// Recharts-backed child pulls a ~370KB chunk; stub to keep test boot fast.
vi.mock('./DashboardCharts', () => ({
  default: () => <div data-testid="dashboard-charts-stub" />,
}))

function makeGuardrailEvent(decision: string, idx = 0): GuardrailEvent {
  return {
    trace_id: `trace-${idx}`,
    event_time: '2026-04-20T10:00:00Z',
    session_id: `session-${idx}`,
    risk_score: 0.9,
    risk_decision: decision,
    severity: 'high',
    request_path: '/agent/stream',
    reasons: ['test'],
  }
}

function makeGuardrailResponse(items: GuardrailEvent[]) {
  return {
    items,
    count: items.length,
    total: items.length,
    offset: 0,
    limit: 100,
  }
}

function createQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

function renderDashboard() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Dashboard — Guardrail Blocks stat card', () => {
  beforeEach(() => {
    fetchEvalTracesMock.mockResolvedValue([])
    fetchQuestionTypesMock.mockResolvedValue([])
    fetchSessionCostSummaryMock.mockResolvedValue({
      total_cost: 0,
      total_requests: 0,
      total_tokens: 0,
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  async function getGuardrailBlocksValue(): Promise<string> {
    const label = await screen.findByText('Guardrail Blocks')
    // StatCard markup: Card > [flex(icon + label-span)] > [div > value-div]
    // Walk: span -> flex div -> Card root.
    const card = label.parentElement?.parentElement
    expect(card).not.toBeNull()
    // The value is the large tabular number — scoped to this card only.
    const valueEl = within(card as HTMLElement).getByText(/^\d+$/)
    return valueEl.textContent ?? ''
  }

  it('counts risk_decision="block" rows (backend canonical vocabulary)', async () => {
    fetchGuardrailEventsMock.mockResolvedValue(
      makeGuardrailResponse([
        makeGuardrailEvent('block', 1),
        makeGuardrailEvent('allow', 2),
        makeGuardrailEvent('block', 3),
      ]),
    )

    renderDashboard()

    await waitFor(async () => {
      // Two blocks expected; a regression to === 'deny' would render 0.
      expect(await getGuardrailBlocksValue()).toBe('2')
    })
  })

  it('still counts legacy risk_decision="deny" rows via shared helper', async () => {
    fetchGuardrailEventsMock.mockResolvedValue(
      makeGuardrailResponse([makeGuardrailEvent('deny', 1)]),
    )

    renderDashboard()

    await waitFor(async () => {
      expect(await getGuardrailBlocksValue()).toBe('1')
    })
  })

  it('renders zero when no blocking decisions are present', async () => {
    fetchGuardrailEventsMock.mockResolvedValue(
      makeGuardrailResponse([
        makeGuardrailEvent('allow', 1),
        makeGuardrailEvent('degraded_allow', 2),
      ]),
    )

    renderDashboard()

    await waitFor(async () => {
      expect(await getGuardrailBlocksValue()).toBe('0')
    })
  })
})
