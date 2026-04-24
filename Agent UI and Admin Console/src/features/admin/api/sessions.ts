import { requestJson } from '@shared/api/http'
import {
  fetchSessionConfig,
  saveSessionConfig,
  type SessionConfig,
} from '@shared/api/sessions'

// ── Re-export shared session config (backward compat) ────────────────────────

export { fetchSessionConfig, saveSessionConfig }
export type { SessionConfig }

// ── Types ────────────────────────────────────────────────────────────────────

export interface SessionSummaryRow {
  session_id: string
  total_cost: number
  total_requests: number
  last_request_at?: string
}

export interface UserAnalyticsRow {
  session_id: string
  trace_count: number
  success_count: number
  error_count: number
  avg_latency_ms: number
  last_active?: string
}

export interface SessionListItem {
  session_id: string
  started_at?: string
  model?: string
  provider?: string
  message_count?: number
  first_question?: string
}

export interface ConversationQuery {
  limit?: number
  cursor?: string | null
  search?: string
}

// ── API ──────────────────────────────────────────────────────────────────────
//
// Admin auth is JWT-cookie-based. `requestJson` sends `credentials: 'include'`
// on every call so the session cookie flows automatically.

export async function fetchSessionCostSummary(): Promise<{
  active_sessions: number
  total_cost: number
  total_requests: number
  sessions: SessionSummaryRow[]
}> {
  return requestJson({ method: 'GET', path: '/agent/sessions/summary' })
}

export async function fetchSessionCost(
  sessionId: string,
): Promise<{
  session_id: string
  total_cost: number
  total_requests: number
  total_tokens?: number
  average_cost_per_request?: number
}> {
  return requestJson({
    method: 'GET',
    path: `/agent/sessions/${encodeURIComponent(sessionId)}/cost`,
  })
}

export async function fetchEvalSessions(
  limit = 100,
): Promise<Array<{ session_id: string; trace_count: number; last_active?: string }>> {
  const response = await requestJson<{
    items: Array<{ session_id: string; trace_count: number; last_active?: string }>
  }>({ method: 'GET', path: '/eval/sessions', query: { limit } })
  return response.items ?? []
}

export async function fetchUserAnalytics(limit = 100): Promise<UserAnalyticsRow[]> {
  const response = await requestJson<{ items: UserAnalyticsRow[] }>({
    method: 'GET',
    path: '/agent/admin/analytics/users',
    query: { limit },
  })
  return response.items ?? []
}

export async function fetchConversationsPage(
  params: ConversationQuery = {},
): Promise<{ items: SessionListItem[]; count: number; limit: number; next_cursor?: string | null }> {
  const response = await requestJson<{
    items: SessionListItem[]
    count: number
    limit: number
    next_cursor?: string | null
  }>({
    method: 'GET',
    path: '/agent/admin/analytics/conversations',
    query: {
      limit: params.limit ?? 100,
      cursor: params.cursor ?? undefined,
      search: params.search?.trim() || undefined,
    },
  })
  return {
    items: response.items ?? [],
    count: response.count ?? 0,
    limit: response.limit ?? (params.limit ?? 100),
    next_cursor: response.next_cursor ?? null,
  }
}
