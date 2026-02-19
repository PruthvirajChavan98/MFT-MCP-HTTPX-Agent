import { API_BASE_URL, requestJson, withAdminHeaders } from './http'
import { streamSse } from './sse'
import type {
  EvalTraceDetail,
  EvalTraceSummary,
  FaqRecord,
  FeedbackRecord,
} from '../types/admin'

// ── Re-export types used by consumers ─────────────────────────────────────────

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

export interface SessionSummaryRow {
  session_id: string
  total_cost: number
  total_requests: number
  last_request_at?: string
}

export interface GuardrailEvent {
  event_time: string
  session_id: string
  risk_score: number
  risk_decision: string
  request_path?: string
  reasons: string[]
}

export interface UserAnalyticsRow {
  session_id: string
  trace_count: number
  success_count: number
  error_count: number
  avg_latency_ms: number
  last_active?: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

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

// ── Eval Traces ───────────────────────────────────────────────────────────────

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

// ── Sessions / Costs ──────────────────────────────────────────────────────────

export async function fetchSessionCostSummary(): Promise<{
  active_sessions: number
  total_cost: number
  total_requests: number
  sessions: SessionSummaryRow[]
}> {
  return requestJson({ method: 'GET', path: '/agent/sessions/summary' })
}

export async function fetchEvalSessions(
  limit = 100,
): Promise<Array<{ session_id: string; trace_count: number; last_active?: string }>> {
  const response = await requestJson<{
    items: Array<{ session_id: string; trace_count: number; last_active?: string }>
  }>({ method: 'GET', path: '/eval/sessions', query: { limit } })
  return response.items ?? []
}

// ── Knowledge Base (FAQ) ──────────────────────────────────────────────────────

export async function fetchFaqs(
  adminKey: string,
  limit = 200,
  skip = 0,
): Promise<FaqRecord[]> {
  const response = await requestJson<{ items: FaqRecord[] }>({
    method: 'GET',
    path: '/agent/admin/faqs',
    query: { limit, skip },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function updateFaq(
  adminKey: string,
  payload: { original_question: string; new_question?: string; new_answer?: string },
): Promise<{ status: string; message?: string }> {
  return requestJson({
    method: 'PUT',
    path: '/agent/admin/faqs',
    headers: withAdminHeaders(adminKey),
    body: payload,
  })
}

export async function deleteFaq(
  adminKey: string,
  question: string,
): Promise<{ status: string; message?: string }> {
  return requestJson({
    method: 'DELETE',
    path: '/agent/admin/faqs',
    query: { question },
    headers: withAdminHeaders(adminKey),
  })
}

export async function ingestFaqBatch(
  adminKey: string,
  items: Array<{ question: string; answer: string }>,
  onProgress?: (message: string) => void,
  openrouterKey?: string,
  groqKey?: string,
): Promise<string> {
  let lastMessage = 'Ingest complete'
  await streamSse(
    `${API_BASE_URL}/agent/admin/faqs/batch-json`,
    {
      method: 'POST',
      headers: withAdminHeaders(adminKey, {
        ...(openrouterKey ? { 'X-OpenRouter-Key': openrouterKey } : {}),
        ...(groqKey ? { 'X-Groq-Key': groqKey } : {}),
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify({ items }),
    },
    {
      onEvent: (eventName, data) => {
        if (eventName === 'error') throw new Error(data || 'FAQ ingest failed')
        if (data) {
          lastMessage = data
          onProgress?.(data)
        }
      },
    },
  )
  return lastMessage
}

// ── Models / Config ───────────────────────────────────────────────────────────

export async function fetchModels(): Promise<
  Array<{ name: string; models: Array<{ id: string; name: string; provider?: string }> }>
> {
  const response = await requestJson<{
    categories: Array<{
      name: string
      models: Array<{ id: string; name: string; provider?: string }>
    }>
  }>({ method: 'GET', path: '/agent/models' })
  return response.categories ?? []
}

export async function fetchSessionConfig(sessionId: string): Promise<{
  session_id: string
  system_prompt?: string
  model_name?: string
  reasoning_effort?: string
  provider?: string
}> {
  return requestJson({
    method: 'GET',
    path: `/agent/config/${encodeURIComponent(sessionId)}`,
  })
}

export async function saveSessionConfig(payload: {
  session_id: string
  system_prompt?: string
  model_name?: string
  reasoning_effort?: string
  provider?: string
  openrouter_api_key?: string
  groq_api_key?: string
}): Promise<{ status: string }> {
  return requestJson({ method: 'POST', path: '/agent/config', body: payload })
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export async function fetchGuardrailEvents(
  adminKey: string,
  limit = 100,
): Promise<GuardrailEvent[]> {
  const response = await requestJson<{ items: GuardrailEvent[] }>({
    method: 'GET',
    path: '/agent/admin/analytics/guardrails',
    query: { limit },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function fetchUserAnalytics(
  adminKey: string,
  limit = 100,
): Promise<UserAnalyticsRow[]> {
  const response = await requestJson<{ items: UserAnalyticsRow[] }>({
    method: 'GET',
    path: '/agent/admin/analytics/users',
    query: { limit },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function fetchConversations(
  adminKey: string,
  limit = 100,
): Promise<EvalTraceSummary[]> {
  const response = await requestJson<{ items: EvalTraceSummary[] }>({
    method: 'GET',
    path: '/agent/admin/analytics/conversations',
    query: { limit },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

// ── Feedback ──────────────────────────────────────────────────────────────────

export async function createFeedback(payload: {
  session_id: string
  trace_id?: string
  rating: 'thumbs_up' | 'thumbs_down'
  comment?: string
  category?: string
}): Promise<{ status: string; id: string }> {
  return requestJson({ method: 'POST', path: '/agent/feedback', body: payload })
}

export async function listFeedback(
  adminKey: string,
  limit = 100,
): Promise<FeedbackRecord[]> {
  const response = await requestJson<{ items: FeedbackRecord[] }>({
    method: 'GET',
    path: '/agent/admin/feedback',
    query: { limit },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function feedbackSummary(adminKey: string): Promise<{
  total: number
  thumbs_up: number
  thumbs_down: number
  positive_rate: number
}> {
  return requestJson({
    method: 'GET',
    path: '/agent/admin/feedback/summary',
    headers: withAdminHeaders(adminKey),
  })
}


// --- System Health & Rate Limiting ---

export interface SystemHealthResponse {
  status: string;
  healthy: boolean;
  checks: Record<string, { ok: boolean;[key: string]: any }>;
  timestamp: number;
}

export async function fetchSystemHealth(): Promise<SystemHealthResponse> {
  return requestJson({ method: 'GET', path: '/health/ready' });
}

export async function fetchRateLimitMetrics(): Promise<any> {
  return requestJson({ method: 'GET', path: '/rate-limit/metrics' });
}

export async function fetchRateLimitConfig(): Promise<any> {
  return requestJson({ method: 'GET', path: '/rate-limit/config' });
}
export { requestJson }

