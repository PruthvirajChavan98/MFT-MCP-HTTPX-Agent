import { requestJson, withAdminHeaders } from '@shared/api/http'

// ── Types ────────────────────────────────────────────────────────────────────

export interface GuardrailEvent {
  trace_id?: string
  event_time: string
  session_id: string
  risk_score: number
  risk_decision: string
  severity?: 'critical' | 'high' | 'medium' | 'low'
  request_path?: string
  reasons: string[]
}

export interface GuardrailSummary {
  total_events: number
  deny_events: number
  allow_events: number
  deny_rate: number
  avg_risk_score: number
}

export interface GuardrailTrendPoint {
  bucket: string
  total_events: number
  deny_events: number
  avg_risk_score: number
}

export interface GuardrailQueueHealth {
  queue_key: string
  depth: number
  dead_letter_queue_key: string
  dead_letter_depth: number
  oldest_age_seconds: number | null
}

export interface GuardrailJudgeFailure {
  trace_id: string
  session_id: string
  model: string
  summary: string
  helpfulness: number
  faithfulness: number
  policy_adherence: number
  evaluated_at: string
}

export interface GuardrailJudgeSummary {
  total_evals: number
  avg_helpfulness: number
  avg_faithfulness: number
  avg_policy_adherence: number
  recent_failures: GuardrailJudgeFailure[]
}

export interface GuardrailEventFilters {
  tenantId?: string
  decision?: string
  minRisk?: number
  sessionId?: string
  start?: string
  end?: string
  offset?: number
  limit?: number
}

// ── API ──────────────────────────────────────────────────────────────────────

export async function fetchGuardrailEvents(
  adminKey: string,
  filters: GuardrailEventFilters = {},
): Promise<{ items: GuardrailEvent[]; count: number; total: number; offset: number; limit: number }> {
  const response = await requestJson<{
    items: GuardrailEvent[]
    count: number
    total: number
    offset: number
    limit: number
  }>({
    method: 'GET',
    path: '/agent/admin/analytics/guardrails',
    query: {
      tenant_id: filters.tenantId ?? 'default',
      decision: filters.decision,
      min_risk: filters.minRisk,
      session_id: filters.sessionId,
      start: filters.start,
      end: filters.end,
      offset: filters.offset ?? 0,
      limit: filters.limit ?? 100,
    },
    headers: withAdminHeaders(adminKey),
  })
  return response
}

export async function fetchGuardrailSummary(
  adminKey: string,
  tenantId = 'default',
): Promise<GuardrailSummary> {
  return requestJson({
    method: 'GET',
    path: '/agent/admin/analytics/guardrails/summary',
    query: { tenant_id: tenantId },
    headers: withAdminHeaders(adminKey),
  })
}

export async function fetchGuardrailTrends(
  adminKey: string,
  tenantId = 'default',
  hours = 24,
): Promise<GuardrailTrendPoint[]> {
  const response = await requestJson<{ items: GuardrailTrendPoint[] }>({
    method: 'GET',
    path: '/agent/admin/analytics/guardrails/trends',
    query: { tenant_id: tenantId, hours },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function fetchGuardrailQueueHealth(adminKey: string): Promise<GuardrailQueueHealth> {
  return requestJson({
    method: 'GET',
    path: '/agent/admin/analytics/guardrails/queue-health',
    headers: withAdminHeaders(adminKey),
  })
}

export async function fetchGuardrailJudgeSummary(
  adminKey: string,
  limitFailures = 20,
): Promise<GuardrailJudgeSummary> {
  return requestJson({
    method: 'GET',
    path: '/agent/admin/analytics/guardrails/judge-summary',
    query: { limit_failures: limitFailures },
    headers: withAdminHeaders(adminKey),
  })
}
