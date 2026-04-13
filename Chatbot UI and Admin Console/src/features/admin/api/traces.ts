import { requestJson } from '@shared/api/http'
import type { ChatMessage as ChatMessageType } from '@shared/types/chat'
import type { EvalTraceDetail, EvalTraceSummary } from '../types/admin'

// ── Types ────────────────────────────────────────────────────────────────────

export interface MetricsSummaryItem {
  metric_name: string
  count: number
  pass_count: number
  pass_rate: number
  avg_score: number
}

export interface MetricFailureItem {
  eval_id: string
  trace_id: string
  metric_name: string
  score: number
  passed: boolean
  reasoning?: string
  updated_at?: string
  provider?: string
  model?: string
  session_id?: string
}

export interface QuestionTypeItem {
  reason: string
  count: number
  pct: number
}

export interface CursorPage<T> {
  items: T[]
  count: number
  limit: number
  next_cursor?: string | null
}

export interface VectorSearchItem {
  labels: string[]
  score: number
  trace_id: string
  event_key?: string | null
  seq?: number | null
  eval_id?: string | null
  metric_name?: string | null
  status?: string
  provider?: string
  model?: string
  session_id?: string
  app_id?: string
  question?: string | null
  final_output?: string | null
  reasoning?: string | null
}

export interface TraceQuery {
  limit?: number
  cursor?: string | null
  search?: string
  status?: string
  model?: string
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function parseQuestion(input: unknown): string {
  if (!input) return ''
  if (typeof input === 'string') {
    try {
      const parsed = JSON.parse(input) as Record<string, unknown>
      return String(parsed.question ?? parsed.input ?? '')
    } catch {
      return ''
    }
  }
  if (typeof input === 'object' && input !== null) {
    const obj = input as Record<string, unknown>
    return String(obj.question ?? obj.input ?? '')
  }
  return ''
}

export function extractTraceQuestion(trace: EvalTraceSummary): string {
  return parseQuestion(trace.inputs_json)
}

// ── API ──────────────────────────────────────────────────────────────────────
//
// Admin auth is JWT-cookie-based. `requestJson` sends `credentials: 'include'`
// on every call so the session cookie flows automatically.

export async function fetchEvalTraces(limit = 100): Promise<EvalTraceSummary[]> {
  const response = await requestJson<{ items: EvalTraceSummary[] }>({
    method: 'GET',
    path: '/eval/search',
    query: { limit, order: 'desc' },
  })
  return response.items ?? []
}

export async function fetchEvalTrace(traceId: string): Promise<EvalTraceDetail> {
  return requestJson<EvalTraceDetail>({
    method: 'GET',
    path: `/eval/trace/${encodeURIComponent(traceId)}`,
  })
}

export async function fetchAdminTrace(traceId: string): Promise<EvalTraceDetail> {
  return requestJson<EvalTraceDetail>({
    method: 'GET',
    path: `/agent/admin/analytics/trace/${encodeURIComponent(traceId)}`,
  })
}

// Backward compatible alias for older imports.
export const fetchCheckpointTrace = fetchAdminTrace

export async function fetchVectorSearch(payload: {
  kind: 'trace' | 'chunk'
  text: string
  k?: number
}): Promise<{
  index: string
  k: number
  min_score: number
  items: VectorSearchItem[]
}> {
  return requestJson({
    method: 'POST',
    path: '/eval/vector-search',
    body: payload,
  })
}

export async function fetchMetricsSummary(): Promise<MetricsSummaryItem[]> {
  const response = await requestJson<{ items: MetricsSummaryItem[] }>({
    method: 'GET',
    path: '/eval/metrics/summary',
  })
  return response.items ?? []
}

export async function fetchMetricFailures(limit = 100): Promise<MetricFailureItem[]> {
  const response = await requestJson<{ items: MetricFailureItem[] }>({
    method: 'GET',
    path: '/eval/metrics/failures',
    query: { limit },
  })
  return response.items ?? []
}

export async function fetchQuestionTypes(limit = 200): Promise<QuestionTypeItem[]> {
  const response = await requestJson<{ items: QuestionTypeItem[] }>({
    method: 'GET',
    path: '/eval/question-types',
    query: { limit },
  })
  return response.items ?? []
}

export async function fetchTraces(limit = 200): Promise<EvalTraceSummary[]> {
  const response = await requestJson<{ items: EvalTraceSummary[] }>({
    method: 'GET',
    path: '/agent/admin/analytics/traces',
    query: { limit },
  })
  return response.items ?? []
}

export async function fetchTracesPage(
  params: TraceQuery = {},
): Promise<CursorPage<EvalTraceSummary>> {
  const response = await requestJson<CursorPage<EvalTraceSummary>>({
    method: 'GET',
    path: '/agent/admin/analytics/traces',
    query: {
      limit: params.limit ?? 200,
      cursor: params.cursor ?? undefined,
      search: params.search?.trim() || undefined,
      status: params.status?.trim() || undefined,
      model: params.model?.trim() || undefined,
    },
  })
  return {
    items: response.items ?? [],
    count: response.count ?? 0,
    limit: response.limit ?? (params.limit ?? 200),
    next_cursor: response.next_cursor ?? null,
  }
}

export async function fetchSessionTraces(
  sessionId: string,
  limit = 500,
): Promise<ChatMessageType[]> {
  const response = await requestJson<{ items: ChatMessageType[] }>({
    method: 'GET',
    path: `/agent/admin/analytics/session/${encodeURIComponent(sessionId)}`,
    query: { limit },
  })
  return response.items ?? []
}
