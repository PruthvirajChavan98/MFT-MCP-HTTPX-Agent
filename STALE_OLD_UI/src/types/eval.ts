export type EvalKind = 'event' | 'trace' | 'result';

export interface EvalSearchItem {
  trace_id: string;
  case_id: string | null;
  session_id: string | null;
  provider: string | null;
  model: string | null;
  endpoint: string | null;
  started_at: string | null;
  ended_at: string | null;
  latency_ms: number | null;
  status: string | null;
  error: string | null;
  event_count: number;
  eval_count: number;
  pass_count: number;

  // --- Router (optional; populate from backend for dashboard display)
  router_sentiment?: string | null;
  router_sentiment_score?: number | null;
  router_reason?: string | null;
  router_reason_score?: number | null;
  router_backend?: string | null;
  router_override?: boolean | null;
  router_override_reason?: string | null;

}

export interface EvalSearchResponse {
  total: number;
  limit: number;
  offset: number;
  items: EvalSearchItem[];
}

// ✅ NEW: Session Clustering Types
export interface SessionClusterItem {
  session_id: string;
  app_id: string | null;
  trace_count: number;
  last_active: string;
  last_model: string | null;
  last_status: string | null;
}

export interface SessionSearchResponse {
  total: number;
  limit: number;
  offset: number;
  items: SessionClusterItem[];
}

export interface EvalEventRow {
  event_key: string;
  trace_id: string;
  seq: number;
  ts: string | null;
  event_type: string | null;
  name: string | null;
  text: string | null;
  payload_json: any;
  meta_json: any;
}

export interface EvalResultRow {
  eval_id: string;
  trace_id: string;
  metric_name: string;
  score: number | null;
  passed: boolean | null;
  reasoning: string | null;
  evaluator_id: string | null;
  meta_json: any;
  evidence_json: any;
  evidence_event_keys: string[];
}

export interface EvalTraceResponse {
  trace: Record<string, any>;
  events: EvalEventRow[];
  evals: EvalResultRow[];
}

export interface FulltextItem {
  labels: string[];
  score: number;
  trace_id: string | null;
  event_key: string | null;
  seq: number | null;
  eval_id: string | null;
  metric_name: string | null;
  preview: string | null;
}

export interface FulltextResponse {
  index: string;
  q: string;
  limit: number;
  offset: number;
  items: FulltextItem[];
}

export interface VectorSearchRequest {
  kind: 'trace' | 'result';
  text?: string | null;
  vector?: number[] | null;
  k?: number;
  min_score?: number;

  // Filters
  provider?: string | null;
  model?: string | null;
  status?: string | null;
  metric_name?: string | null;
  passed?: boolean | null;

  // ✅ NEW IDs
  session_id?: string | null;
  case_id?: string | null;
}

export interface VectorSearchItem {
  labels: string[];
  score: number;
  trace_id: string | null;
  event_key: string | null;
  seq: number | null;
  eval_id: string | null;
  metric_name: string | null;
  status: string | null;
  provider: string | null;
  model: string | null;

  // ✅ NEW Fields for UI & Filtering
  session_id?: string | null;
  app_id?: string | null; // Mapped from case_id

  question?: string | null;
  final_output?: string | null;
  reasoning?: string | null;
}

export interface VectorSearchResponse {
  index: string;
  k: number;
  min_score: number;
  items: VectorSearchItem[];
}

export interface MetricSummaryRow {
  metric_name: string;
  total: number;
  pass_count: number;
  fail_count: number;
  pass_rate: number; // 0..1
}

export interface MetricSummaryResponse {
  items: MetricSummaryRow[];
  total_metrics: number;
  total_evals: number;
  overall_pass_rate: number; // 0..1
}

export interface MetricFailureRow {
  eval_id: string;
  trace_id: string;
  metric_name: string;
  score: number | null;
  passed: boolean;
  evaluator_id: string | null;
  reasoning: string | null;
  updated_at: string | null;

  trace_status: string | null;
  provider: string | null;
  model: string | null;
  endpoint: string | null;
  session_id: string | null;
  case_id: string | null;
  started_at: string | null;
}

export interface MetricFailuresResponse {
  limit: number;
  offset: number;
  items: MetricFailureRow[];
}

export interface QuestionTypeRow {
  reason: string;
  count: number;
  pct: number;
}
export interface QuestionTypesResponse {
  limit: number;
  total: number;
  items: QuestionTypeRow[];
}
