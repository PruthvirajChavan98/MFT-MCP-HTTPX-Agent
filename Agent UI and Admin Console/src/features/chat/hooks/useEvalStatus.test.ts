import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useEvalStatus } from './useEvalStatus'

vi.mock('@shared/api/http', () => ({ API_BASE_URL: '/api' }))

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response
}

describe('useEvalStatus', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.useFakeTimers()
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('returns null when traceId is undefined', () => {
    const { result } = renderHook(() => useEvalStatus(undefined))

    expect(result.current).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('polls and returns complete status', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        status: 'complete',
        inline_evals: { passed: 2, failed: 1 },
        shadow_judge: null,
      }),
    )

    const { result } = renderHook(() => useEvalStatus('trace-123'))

    // First fetch fires immediately
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/api/eval/trace/trace-123/eval-status')
    expect(result.current).toEqual({
      status: 'complete',
      reason: undefined,
      passed: 2,
      failed: 1,
      shadowJudge: undefined,
    })

    // Advance past one interval — no further fetch because status was complete
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('polls pending then complete', async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({ status: 'pending' }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: 'complete',
          inline_evals: { passed: 3, failed: 0 },
          shadow_judge: { helpfulness: 0.9, faithfulness: 0.8, policy_adherence: 1.0 },
        }),
      )

    const { result } = renderHook(() => useEvalStatus('trace-456'))

    // Immediate first fetch — pending
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(result.current).toEqual({
      status: 'pending',
      reason: undefined,
      passed: undefined,
      failed: undefined,
      shadowJudge: undefined,
    })

    // Advance one interval — second fetch returns complete
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(result.current).toEqual({
      status: 'complete',
      reason: undefined,
      passed: 3,
      failed: 0,
      shadowJudge: { helpfulness: 0.9, faithfulness: 0.8, policy_adherence: 1.0 },
    })

    // No further polling after complete
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('returns not_found on 404', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(null, 404))

    const { result } = renderHook(() => useEvalStatus('trace-missing'))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(result.current).toEqual({
      status: 'not_found',
      reason: undefined,
      passed: undefined,
      failed: undefined,
      shadowJudge: undefined,
    })

    // Should not poll further
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('returns unavailable after max attempts when always pending', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve(jsonResponse({ status: 'pending' })),
    )

    const { result } = renderHook(() => useEvalStatus('trace-forever'))

    // Immediate first fetch (attempt 1)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    // Advance through 9 more intervals (attempts 2-10)
    for (let i = 0; i < 9; i++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5_000)
      })
    }

    expect(fetchMock).toHaveBeenCalledTimes(10)

    // Attempt 11 should NOT fire
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })

    expect(fetchMock).toHaveBeenCalledTimes(10)
    expect(result.current).toEqual({
      status: 'unavailable',
      reason: 'timed_out',
      passed: undefined,
      failed: undefined,
      shadowJudge: undefined,
    })
  })

  it('stops polling when backend returns unavailable', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        status: 'unavailable',
        reason: 'sampled_out',
        shadow_judge: null,
      }),
    )

    const { result } = renderHook(() => useEvalStatus('trace-unavailable'))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(result.current).toEqual({
      status: 'unavailable',
      reason: 'sampled_out',
      passed: undefined,
      failed: undefined,
      shadowJudge: undefined,
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('encodes traceId in the URL', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ status: 'complete', inline_evals: { passed: 1, failed: 0 } }),
    )

    renderHook(() => useEvalStatus('trace/with spaces&special'))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/eval/trace/trace%2Fwith%20spaces%26special/eval-status',
    )
  })

  it('cleans up interval on unmount', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve(jsonResponse({ status: 'pending' })),
    )

    const { unmount } = renderHook(() => useEvalStatus('trace-cleanup'))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)

    unmount()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })

    // No further fetches after unmount
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
