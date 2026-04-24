import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useDebouncedLoading } from './useDebouncedLoading'

describe('useDebouncedLoading', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('stays false while the load completes before the delay', () => {
    const { result, rerender } = renderHook(
      ({ loading }) => useDebouncedLoading(loading, 200),
      { initialProps: { loading: false } },
    )

    rerender({ loading: true })
    expect(result.current).toBe(false)

    act(() => {
      vi.advanceTimersByTime(150)
    })
    rerender({ loading: false })
    act(() => {
      vi.advanceTimersByTime(100)
    })

    expect(result.current).toBe(false)
  })

  it('flips to true once loading outlasts the delay', () => {
    const { result, rerender } = renderHook(
      ({ loading }) => useDebouncedLoading(loading, 200),
      { initialProps: { loading: false } },
    )

    rerender({ loading: true })
    expect(result.current).toBe(false)

    act(() => {
      vi.advanceTimersByTime(250)
    })

    expect(result.current).toBe(true)
  })

  it('resets to false immediately when loading drops', () => {
    const { result, rerender } = renderHook(
      ({ loading }) => useDebouncedLoading(loading, 200),
      { initialProps: { loading: true } },
    )

    act(() => {
      vi.advanceTimersByTime(250)
    })
    expect(result.current).toBe(true)

    rerender({ loading: false })
    expect(result.current).toBe(false)
  })
})
