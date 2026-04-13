import type { ReactNode } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { GlobalTraceSheet } from './GlobalTraceSheet'

const { useQueryMock } = vi.hoisted(() => ({
  useQueryMock: vi.fn(),
}))

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query')
  return {
    ...actual,
    useQuery: useQueryMock,
  }
})

vi.mock('@components/ui/split-pane', () => ({
  SplitPane: ({
    sidebar,
    main,
  }: {
    sidebar: ReactNode
    main: ReactNode
  }) => (
    <div>
      <div>{sidebar}</div>
      <div>{main}</div>
    </div>
  ),
}))

vi.mock('@components/ui/sheet', () => ({
  Sheet: ({ open, children }: { open: boolean; children: ReactNode }) =>
    open ? <div data-testid="sheet-root">{children}</div> : null,
  SheetContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  SheetTitle: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>
}

describe('GlobalTraceSheet', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    useQueryMock.mockReturnValue({
      data: {
        trace: {
          trace_id: 'trace-1',
          session_id: 'session-1',
          model: 'openai/gpt-oss-120b',
          started_at: '2026-04-03T10:00:00.000Z',
          ended_at: '2026-04-03T10:00:02.000Z',
          latency_ms: 2000,
          status: 'success',
          inputs_json: { input: 'hello' },
          final_output: 'world',
        },
        events: [],
        evals: [],
      },
      isLoading: false,
      error: null,
    })
  })

  it('clears traceId from the current route when the Back button is clicked', () => {
    render(
      <MemoryRouter initialEntries={['/admin/dashboard?traceId=trace-1']}>
        <LocationProbe />
        <GlobalTraceSheet />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Back to traces' }))

    expect(screen.getByTestId('location')).toHaveTextContent('/admin/dashboard')
    expect(screen.queryByTestId('sheet-root')).not.toBeInTheDocument()
  })

  it('mounts the shared sheet on the dedicated traces route and clears traceId on Back', () => {
    render(
      <MemoryRouter initialEntries={['/admin/traces?traceId=trace-1']}>
        <LocationProbe />
        <GlobalTraceSheet />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('sheet-root')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Back to traces' }))

    expect(screen.getByTestId('location')).toHaveTextContent('/admin/traces')
    expect(screen.queryByTestId('sheet-root')).not.toBeInTheDocument()
  })
})
