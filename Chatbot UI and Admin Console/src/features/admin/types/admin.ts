export interface EvalTraceSummary {
  trace_id: string
  session_id: string
  provider?: string
  model?: string
  endpoint?: string
  started_at?: string
  latency_ms?: number
  status?: string
  error?: string
  inputs_json?: unknown
  final_output?: string
  reasoning?: string
  scores?: Array<{ name: string; score: number; passed: boolean }>
}

export interface EvalTraceDetail {
  trace: {
    trace_id: string
    session_id: string
    provider?: string
    model?: string
    endpoint?: string
    started_at?: string
    ended_at?: string
    latency_ms?: number
    status?: string
    error?: string
    inputs_json?: unknown
    final_output?: string
  }
  events: Array<{
    event_key: string
    seq: number
    ts?: string
    event_type?: string
    name?: string
    text?: string
    payload_json?: unknown
  }>
  evals: Array<{
    eval_id: string
    metric_name: string
    score: number
    passed: boolean
    reasoning?: string
  }>
}

export type FaqVectorStatus = 'pending' | 'syncing' | 'synced' | 'failed'

export interface FaqRecord {
  id?: string
  question: string
  answer: string
  category?: string
  tags?: string[]
  vector_status?: FaqVectorStatus
  vectorized?: boolean
  vector_error?: string | null
  vector_updated_at?: string | null
  created_at?: string
  updated_at?: string
}

export interface FaqCategory {
  id: string
  slug: string
  label: string
  is_active: boolean
}

export interface FeedbackRecord {
  id: string
  session_id: string
  trace_id?: string | null
  rating: 'thumbs_up' | 'thumbs_down'
  comment?: string | null
  category?: string | null
  created_at: string
}
