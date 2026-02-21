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

export interface FaqRecord {
  question: string
  answer: string
  created_at?: string
  updated_at?: string
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
