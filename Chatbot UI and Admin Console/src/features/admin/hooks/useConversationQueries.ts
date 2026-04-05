import { useMemo } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import {
  fetchConversationsPage,
  fetchEvalSessions,
  fetchSessionCost,
  fetchSessionTraces,
} from '@features/admin/api/admin'
import type { SessionListItem } from '@features/admin/api/admin'
import type { ChatMessage } from '@shared/types/chat'

const PAGE_SIZE = 80

/**
 * Stable staleTime prevents skeleton flash when switching between
 * previously-viewed sessions. The traces are immutable after creation,
 * so 5 minutes of staleness is safe.
 */
const SESSION_TRACES_STALE_MS = 5 * 60 * 1000

/**
 * Cost data can be slightly stale — 30s polling already handles freshness.
 * The staleTime prevents refetch on every focus/selection change.
 */
const SESSION_COST_STALE_MS = 15_000
const SESSION_COST_REFETCH_MS = 30_000

interface ConversationQueriesParams {
  adminKey: string
  deferredSearch: string
  sessionId: string | null
}

export function useConversationQueries({
  adminKey,
  deferredSearch,
  sessionId,
}: ConversationQueriesParams) {
  // ── Paginated conversation list ───────────────────────────────────────────
  const conversationsQuery = useInfiniteQuery({
    queryKey: ['conversations-page', adminKey, deferredSearch] as const,
    queryFn: ({ pageParam }) =>
      fetchConversationsPage(adminKey, {
        limit: PAGE_SIZE,
        cursor: (pageParam as string | undefined) ?? undefined,
        search: deferredSearch,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor || undefined,
    /**
     * Keep old pages visible while new search results load.
     * This prevents the list from going blank during typing.
     */
    placeholderData: (previousData) => previousData,
  })

  const conversations = useMemo(
    () => conversationsQuery.data?.pages.flatMap((page) => page.items ?? []) ?? [],
    [conversationsQuery.data],
  )

  // ── Eval sessions (separate tab) ──────────────────────────────────────────
  const evalSessionsQuery = useQuery({
    queryKey: ['eval-sessions', adminKey] as const,
    queryFn: () => fetchEvalSessions(adminKey, 100),
  })

  // ── Session transcript ────────────────────────────────────────────────────
  const sessionTracesQuery = useQuery({
    queryKey: ['session-traces', adminKey, sessionId] as const,
    queryFn: () => fetchSessionTraces(adminKey, sessionId!),
    enabled: sessionId !== null,
    staleTime: SESSION_TRACES_STALE_MS,
  })

  // ── Session cost ──────────────────────────────────────────────────────────
  const sessionCostQuery = useQuery({
    queryKey: ['session-cost-detail', sessionId] as const,
    queryFn: () => fetchSessionCost(sessionId!),
    enabled: sessionId !== null,
    staleTime: SESSION_COST_STALE_MS,
    refetchInterval: SESSION_COST_REFETCH_MS,
  })

  return {
    // List
    conversations,
    conversationsQuery,
    // Eval
    evalSessions: evalSessionsQuery.data ?? [],
    evalLoading: evalSessionsQuery.isLoading,
    // Transcript
    sessionTraces: sessionTracesQuery.data ?? [],
    sessionTracesLoading: sessionTracesQuery.isLoading,
    // Cost
    sessionCost: sessionCostQuery.data ?? null,
  }
}

/**
 * Resolve the selected session metadata.
 *
 * Priority:
 * 1. Match from the paginated conversation list (full metadata)
 * 2. Derive minimal metadata from loaded session traces (fallback)
 * 3. null if no sessionId is selected
 *
 * Returns a discriminated union so callers know whether they have
 * full metadata or a degraded fallback.
 */
export type ResolvedSession =
  | { kind: 'full'; data: SessionListItem }
  | { kind: 'partial'; data: PartialSessionInfo }
  | null

export interface PartialSessionInfo {
  session_id: string
  started_at?: string
  model?: string
  provider?: string
}

export function resolveSelectedSession(
  sessionId: string | null,
  conversations: SessionListItem[],
  sessionTraces: ChatMessage[],
): ResolvedSession {
  if (!sessionId) return null

  const fromList = conversations.find((c) => c.session_id === sessionId)
  if (fromList) return { kind: 'full', data: fromList }

  // Degraded fallback — the session exists but isn't in the current page/search
  const firstAssistant = sessionTraces.find((m) => m.role === 'assistant')
  return {
    kind: 'partial',
    data: {
      session_id: sessionId,
      started_at: sessionTraces.length
        ? new Date(sessionTraces[0].timestamp).toISOString()
        : undefined,
      model: firstAssistant?.model || undefined,
      provider: firstAssistant?.provider || undefined,
    },
  }
}
