import { buildConversationHref } from '@features/admin/lib/admin-links'
import { trailingBuckets, type Granularity } from '@features/admin/lib/time-bucket'
import type { SessionSummaryRow } from '@features/admin/api/admin'

export type SessionCostSummary = {
  active_sessions: number
  total_cost: number
  total_requests: number
  sessions: SessionSummaryRow[]
}

export type CostSeriesPoint = {
  /** Compact label used as the x-axis tick — first 8 chars of the
   *  session_id (uppercased) so every bar is uniquely interpretable at
   *  a glance. The full session_id is on the datum for the tooltip. */
  name: string
  /** Ordinal 1-based rank by cost (S1 = most expensive) — retained so
   *  the tooltip can show rank alongside the truncated ID. */
  rank: number
  sessionId: string
  lastActive?: string
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
 * Strip hex-style separators and return a short identifier that is
 * distinguishable across top-12 sessions. Falls back to the raw id if
 * the session_id is already shorter than the cap.
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

export type CostOverTimePoint = {
  /** YYYY-MM-DD bucket key (Monday for week; first-of-month for month). */
  bucket: string
  /** Human-facing label (e.g. "Apr 4", "Apr 2026"). */
  label: string
  /**
   * Mirrors ``label`` so the existing ``CostTooltip`` predicate (which
   * checks for a ``name`` field) picks up the bucket caption without a
   * second tooltip implementation.
   */
  name: string
  /** Summed cost in USD for the bucket. */
  cost: number
}

/**
 * Re-bucket the same session rows the Cost-by-Session chart uses into a
 * time-axis series. Uses each session's ``last_request_at`` as the
 * activity anchor — not perfect for sessions with long tails, but the
 * truest single-field approximation the current API surface exposes. A
 * future plan can push ``DATE_TRUNC(hour, cost_events.at)`` server-side
 * for proper per-event granularity.
 */
export function mapCostOverTime(
  summary: SessionCostSummary | undefined,
  granularity: Granularity,
): CostOverTimePoint[] {
  const rows = summary?.sessions ?? []
  return trailingBuckets(
    rows,
    (s) => s.last_request_at,
    (s) => s.total_cost,
    granularity,
  ).map((p) => ({ bucket: p.bucket, label: p.label, name: p.label, cost: p.value }))
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
    series: sessions.slice(0, SERIES_LIMIT).map((session, index) => ({
      name: shortSessionLabel(session.session_id),
      rank: index + 1,
      sessionId: session.session_id,
      lastActive: session.last_request_at,
      cost: session.total_cost,
      requests: session.total_requests,
    })),
  }
}
