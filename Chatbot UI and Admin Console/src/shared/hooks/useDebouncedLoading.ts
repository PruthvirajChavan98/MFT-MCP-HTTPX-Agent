import { useEffect, useState } from 'react'

/**
 * Returns `true` only after `loading` has been truthy continuously for
 * at least `delayMs`. Prevents skeleton flicker on sub-threshold refetches.
 *
 * Why: React Query flips `isFetching` to true during background refetch
 * even on cache hits. Without a delay, the UI flashes skeletons for
 * <100ms, which reads as "flaky."
 */
export function useDebouncedLoading(loading: boolean, delayMs = 200): boolean {
  const [debounced, setDebounced] = useState(loading)

  useEffect(() => {
    if (!loading) {
      setDebounced(false)
      return
    }
    const timer = window.setTimeout(() => setDebounced(true), delayMs)
    return () => window.clearTimeout(timer)
  }, [loading, delayMs])

  return debounced
}
