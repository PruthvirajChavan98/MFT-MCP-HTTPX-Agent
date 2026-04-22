import { buildConversationHref } from '@features/admin/lib/admin-links'
import type { SessionSummaryRow } from '@features/admin/api/admin'

export type SessionCostSummary = {
  active_sessions: number
  total_cost: number
  total_requests: number
  sessions: SessionSummaryRow[]
}

export type CostSeriesPoint = {
  name: string
  sessionId: string
  cost: number
  requests: number
}

export type CostSessionRow = {
  sessionId: string
  requests: number
  cost: number
  lastActive?: string
  conversationHref: string | null
}

export type CostDashboardViewModel = {
  activeSessions: number
  totalRequests: number
  totalCost: number
  sessions: CostSessionRow[]
  series: CostSeriesPoint[]
}

const SERIES_LIMIT = 12

/**
 * Compact, stable identifier used as the bar chart tick. First 8 chars of
 * the session_id with dashes/underscores stripped so every bar cross-
 * references exactly one row in the Sessions list — replaces the prior
 * `S1, S2, …` ordinal labels which were unreadable and non-unique across
 * refreshes.
 */
function shortSessionLabel(sessionId: string): string {
  const trimmed = (sessionId || '').replace(/[-_]/g, '')
  return trimmed.slice(0, 8) || sessionId || '—'
}

function byCostThenRequestsDesc(a: SessionSummaryRow, b: SessionSummaryRow): number {
  if (b.total_cost !== a.total_cost) return b.total_cost - a.total_cost
  if (b.total_requests !== a.total_requests) return b.total_requests - a.total_requests
  const aLast = a.last_request_at || ''
  const bLast = b.last_request_at || ''
  return bLast.localeCompare(aLast)
}

export function mapSessionCostSummary(summary?: SessionCostSummary): CostDashboardViewModel {
  const sessions = [...(summary?.sessions ?? [])].sort(byCostThenRequestsDesc)

  return {
    activeSessions: summary?.active_sessions ?? 0,
    totalRequests: summary?.total_requests ?? 0,
    totalCost: summary?.total_cost ?? 0,
    sessions: sessions.map((session) => ({
      sessionId: session.session_id,
      requests: session.total_requests,
      cost: session.total_cost,
      lastActive: session.last_request_at,
      conversationHref: buildConversationHref(session.session_id),
    })),
    series: sessions.slice(0, SERIES_LIMIT).map((session) => ({
      name: shortSessionLabel(session.session_id),
      sessionId: session.session_id,
      cost: session.total_cost,
      requests: session.total_requests,
    })),
  }
}
