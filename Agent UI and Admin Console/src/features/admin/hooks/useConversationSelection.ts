import { useCallback, useDeferredValue, useMemo } from 'react'
import { useSearchParams } from 'react-router'

/**
 * URL-as-single-source-of-truth for conversation selection and search.
 *
 * Design:
 * - `sessionId` and `search` are read directly from URLSearchParams
 * - No React state duplicates — all mutations go through `setSearchParams`
 * - `deferredSearch` is used for query keys so typing doesn't cause
 *   immediate query invalidation + page flash
 * - Selection survives search transitions because the URL param persists
 *   independently of the conversation list contents
 */
export function useConversationSelection() {
  const [searchParams, setSearchParams] = useSearchParams()

  const sessionId = searchParams.get('sessionId') ?? null
  const search = searchParams.get('search') ?? ''
  const deferredSearch = useDeferredValue(search)

  const setSearch = useCallback(
    (value: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          const trimmed = value.trim()
          if (trimmed) next.set('search', trimmed)
          else next.delete('search')
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const selectSession = useCallback(
    (id: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set('sessionId', id)
          return next
        },
        { replace: false },
      )
    },
    [setSearchParams],
  )

  const clearSession = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('sessionId')
        return next
      },
      { replace: true },
    )
  }, [setSearchParams])

  return useMemo(
    () => ({
      sessionId,
      search,
      deferredSearch,
      setSearch,
      selectSession,
      clearSession,
    }),
    [sessionId, search, deferredSearch, setSearch, selectSession, clearSession],
  )
}
