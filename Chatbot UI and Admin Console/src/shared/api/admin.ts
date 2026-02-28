import { API_BASE_URL, requestJson, withAdminHeaders } from './http'
import { streamSse } from './sse'
import type { ChatMessage as ChatMessageType } from '../types/chat'
import type {
  EvalTraceDetail,
  EvalTraceSummary,
  FaqCategory,
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

export interface UserAnalyticsRow {
  session_id: string
  trace_count: number
  success_count: number
  error_count: number
  avg_latency_ms: number
  last_active?: string
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

export async function fetchEvalTraces(
  adminKey: string,
  limit = 100,
): Promise<EvalTraceSummary[]> {
  const response = await requestJson<{ items: EvalTraceSummary[] }>({
    method: 'GET',
    path: '/eval/search',
    query: { limit, order: 'desc' },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function fetchEvalTrace(adminKey: string, traceId: string): Promise<EvalTraceDetail> {
  return requestJson<EvalTraceDetail>({
    method: 'GET',
    path: `/eval/trace/${encodeURIComponent(traceId)}`,
    headers: withAdminHeaders(adminKey),
  })
}

export async function fetchAdminTrace(adminKey: string, traceId: string): Promise<EvalTraceDetail> {
  return requestJson<EvalTraceDetail>({
    method: 'GET',
    path: `/agent/admin/analytics/trace/${encodeURIComponent(traceId)}`,
    headers: withAdminHeaders(adminKey),
  })
}

// Backward compatible alias for older imports.
export const fetchCheckpointTrace = fetchAdminTrace

export async function fetchVectorSearch(payload: {
  adminKey: string
  kind: 'trace' | 'chunk'
  text: string
  k?: number
}): Promise<{
  index: string
  k: number
  min_score: number
  items: VectorSearchItem[]
}> {
  const { adminKey, ...body } = payload
  return requestJson({
    method: 'POST',
    path: '/eval/vector-search',
    body,
    headers: withAdminHeaders(adminKey),
  })
}

export async function fetchMetricsSummary(adminKey: string): Promise<MetricsSummaryItem[]> {
  const response = await requestJson<{ items: MetricsSummaryItem[] }>({
    method: 'GET',
    path: '/eval/metrics/summary',
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function fetchMetricFailures(
  adminKey: string,
  limit = 100,
): Promise<MetricFailureItem[]> {
  const response = await requestJson<{ items: MetricFailureItem[] }>({
    method: 'GET',
    path: '/eval/metrics/failures',
    query: { limit },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function fetchQuestionTypes(
  adminKey: string,
  limit = 200,
): Promise<QuestionTypeItem[]> {
  const response = await requestJson<{ items: QuestionTypeItem[] }>({
    method: 'GET',
    path: '/eval/question-types',
    query: { limit },
    headers: withAdminHeaders(adminKey),
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
  adminKey: string,
  limit = 100,
): Promise<Array<{ session_id: string; trace_count: number; last_active?: string }>> {
  const response = await requestJson<{
    items: Array<{ session_id: string; trace_count: number; last_active?: string }>
  }>({ method: 'GET', path: '/eval/sessions', query: { limit }, headers: withAdminHeaders(adminKey) })
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
  payload: {
    id?: string
    original_question?: string
    new_question?: string
    new_answer?: string
    new_category?: string
    new_tags?: string[]
  },
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
  target: string | { id?: string; question?: string },
): Promise<{ status: string; message?: string }> {
  const query =
    typeof target === 'string'
      ? { question: target }
      : {
          ...(target.id ? { id: target.id } : {}),
          ...(target.question ? { question: target.question } : {}),
        }
  return requestJson({
    method: 'DELETE',
    path: '/agent/admin/faqs',
    query,
    headers: withAdminHeaders(adminKey),
  })
}

export async function clearAllFaqs(
  adminKey: string,
): Promise<{ status: string; message?: string }> {
  return requestJson({
    method: 'DELETE',
    path: '/agent/admin/faqs/all',
    headers: withAdminHeaders(adminKey),
  })
}

export async function fetchFaqCategories(adminKey: string): Promise<FaqCategory[]> {
  const response = await requestJson<{ items: FaqCategory[] }>({
    method: 'GET',
    path: '/agent/admin/faq-categories',
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function searchFaqSemantic(
  adminKey: string,
  query: string,
  limit = 5,
  openrouterKey?: string,
  groqKey?: string,
): Promise<Array<{ question: string; answer: string; score: number }>> {
  const response = await requestJson<{ status: string; results: Array<{ question: string; answer: string; score: number }> }>({
    method: 'POST',
    path: '/agent/admin/faqs/semantic-search',
    headers: withAdminHeaders(adminKey, {
      ...(openrouterKey ? { 'X-OpenRouter-Key': openrouterKey } : {}),
      ...(groqKey ? { 'X-Groq-Key': groqKey } : {}),
    }),
    body: { query, limit },
  })
  return response.results ?? []
}

function resolveSseErrorMessage(data: string, parsed?: unknown): string {
  if (parsed && typeof parsed === 'object') {
    const payload = parsed as {
      message?: string
      detail?: string | { message?: string; detail?: string }
    }
    if (typeof payload.message === 'string' && payload.message.trim()) return payload.message.trim()
    if (typeof payload.detail === 'string' && payload.detail.trim()) return payload.detail.trim()
    if (payload.detail && typeof payload.detail === 'object') {
      if (
        typeof payload.detail.message === 'string' &&
        payload.detail.message.trim()
      ) {
        return payload.detail.message.trim()
      }
      if (
        typeof payload.detail.detail === 'string' &&
        payload.detail.detail.trim()
      ) {
        return payload.detail.detail.trim()
      }
    }
  }
  if (data.trim()) return data
  return 'FAQ ingest failed'
}

export async function ingestFaqBatch(
  adminKey: string,
  items: Array<{ question: string; answer: string; category?: string; tags?: string[] }>,
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
      onEvent: (eventName, data, parsed) => {
        if (eventName === 'error') throw new Error(resolveSseErrorMessage(data, parsed))
        if (data) {
          lastMessage = data
          onProgress?.(data)
        }
      },
    },
  )
  return lastMessage
}

export async function ingestFaqPdf(
  adminKey: string,
  file: File,
  onProgress?: (message: string) => void,
  openrouterKey?: string,
  groqKey?: string,
): Promise<string> {
  let lastMessage = 'PDF ingest complete'
  const formData = new FormData()
  formData.append('file', file)

  await streamSse(
    `${API_BASE_URL}/agent/admin/faqs/upload-pdf`,
    {
      method: 'POST',
      headers: withAdminHeaders(adminKey, {
        ...(openrouterKey ? { 'X-OpenRouter-Key': openrouterKey } : {}),
        ...(groqKey ? { 'X-Groq-Key': groqKey } : {}),
      }),
      body: formData,
    },
    {
      onEvent: (eventName, data, parsed) => {
        if (eventName === 'error') throw new Error(resolveSseErrorMessage(data, parsed))
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

export async function fetchConversations(
  adminKey: string,
  limit = 100,
): Promise<SessionListItem[]> {
  const response = await requestJson<{ items: SessionListItem[] }>({
    method: 'GET',
    path: '/agent/admin/analytics/conversations',
    query: { limit },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function fetchConversationsPage(
  adminKey: string,
  params: ConversationQuery = {},
): Promise<CursorPage<SessionListItem>> {
  const response = await requestJson<CursorPage<SessionListItem>>({
    method: 'GET',
    path: '/agent/admin/analytics/conversations',
    query: {
      limit: params.limit ?? 100,
      cursor: params.cursor ?? undefined,
      search: params.search?.trim() || undefined,
    },
    headers: withAdminHeaders(adminKey),
  })
  return {
    items: response.items ?? [],
    count: response.count ?? 0,
    limit: response.limit ?? (params.limit ?? 100),
    next_cursor: response.next_cursor ?? null,
  }
}

export interface TraceQuery {
  limit?: number
  cursor?: string | null
  search?: string
  status?: string
  model?: string
}

export async function fetchTraces(
  adminKey: string,
  limit = 200,
): Promise<EvalTraceSummary[]> {
  const response = await requestJson<{ items: EvalTraceSummary[] }>({
    method: 'GET',
    path: '/agent/admin/analytics/traces',
    query: { limit },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function fetchTracesPage(
  adminKey: string,
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
    headers: withAdminHeaders(adminKey),
  })
  return {
    items: response.items ?? [],
    count: response.count ?? 0,
    limit: response.limit ?? (params.limit ?? 200),
    next_cursor: response.next_cursor ?? null,
  }
}

export async function fetchSessionTraces(
  adminKey: string,
  sessionId: string,
  limit = 500,
): Promise<ChatMessageType[]> {
  const response = await requestJson<{ items: ChatMessageType[] }>({
    method: 'GET',
    path: `/agent/admin/analytics/session/${encodeURIComponent(sessionId)}`,
    query: { limit },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
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
