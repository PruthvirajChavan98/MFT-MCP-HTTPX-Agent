import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatTracesPage } from './ChatTracesPage'

const { useInfiniteQueryMock } = vi.hoisted(() => ({
  useInfiniteQueryMock: vi.fn(),
}))

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query')
  return {
    ...actual,
    useInfiniteQuery: useInfiniteQueryMock,
  }
})

vi.mock('./MetricsDashboard', () => ({
  MetricsDashboard: () => <div>Metrics dashboard</div>,
}))

vi.mock('./SemanticSearchUI', () => ({
  SemanticSearchUI: () => <div>Semantic search</div>,
}))

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>
}

describe('ChatTracesPage', () => {
  beforeEach(() => {
    useInfiniteQueryMock.mockReturnValue({
      data: {
        pages: [
          {
            items: [
              {
                trace_id: 'trace-1',
                session_id: 'session-1',
                model: 'openai/gpt-oss-120b',
                inputs_json: { input: 'hello' },
                final_output: 'world',
              },
            ],
          },
        ],
      },
      isLoading: false,
      error: null,
      hasNextPage: false,
      isFetchingNextPage: false,
      fetchNextPage: vi.fn(),
    })

  })

  it('writes traceId into the URL when Inspect is clicked without rendering an inline explorer', () => {
    render(
      <MemoryRouter initialEntries={['/admin/traces']}>
        <Routes>
          <Route
            path="/admin/traces"
            element={
              <>
                <LocationProbe />
                <ChatTracesPage />
              </>
            }
          />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: /inspect/i }))

    expect(screen.getByTestId('location')).toHaveTextContent('/admin/traces?traceId=trace-1')
    expect(screen.queryByRole('button', { name: 'Back to traces' })).not.toBeInTheDocument()
  }, 15000)
})
