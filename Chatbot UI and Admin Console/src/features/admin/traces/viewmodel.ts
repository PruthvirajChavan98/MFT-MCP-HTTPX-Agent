import type { EvalTraceDetail, EvalTraceSummary } from '@features/admin/types/admin'
import { buildConversationHref } from '@features/admin/lib/admin-links'
import type { TraceDetail } from './trace-viewer/types'

export type TraceListRow = {
  traceId: string
  sessionId: string
  model: string
  status: 'success' | 'error'
  startedAt?: string
  inputPreview: string
  conversationHref: string | null
}

function parseQuestionInput(input: unknown): string {
  if (!input) return ''

  if (typeof input === 'string') {
    const raw = input.trim()
    if (!raw) return ''
    try {
      const parsed = JSON.parse(raw)
      return parseQuestionInput(parsed)
    } catch {
      return raw
    }
  }

  if (typeof input !== 'object') return ''

  const asRecord = input as Record<string, unknown>
  const question = asRecord.question
  if (typeof question === 'string' && question.trim()) return question.trim()

  const textInput = asRecord.input
  if (typeof textInput === 'string' && textInput.trim()) return textInput.trim()

  return ''
}

export function getTraceInputPreview(trace: Pick<EvalTraceSummary, 'inputs_json' | 'final_output'>): string {
  return parseQuestionInput(trace.inputs_json) || trace.final_output?.slice(0, 120) || '—'
}

export function mapTraceListRows(traces: EvalTraceSummary[]): TraceListRow[] {
  return traces.map((trace) => ({
    traceId: trace.trace_id,
    sessionId: trace.session_id,
    model: trace.model || '—',
    status: trace.error ? 'error' : 'success',
    startedAt: trace.started_at,
    inputPreview: getTraceInputPreview(trace),
    conversationHref: buildConversationHref(trace.session_id),
  }))
}

export function mapTraceDetailToViewer(detail?: EvalTraceDetail | null): TraceDetail | null {
  if (!detail) return null

  return {
    trace: {
      name: detail.trace?.trace_id || 'Agent Trace',
      started_at: detail.trace?.started_at,
      ended_at: detail.trace?.ended_at,
      latency_ms: detail.trace?.latency_ms,
      status: detail.trace?.status,
      inputs_json: detail.trace?.inputs_json,
      final_output: detail.trace?.final_output,
      model: detail.trace?.model,
    },
    events: detail.events?.map((event) => ({
      seq: event.seq,
      ts: event.ts,
      event_type: event.event_type,
      name: event.name,
      event_key: event.event_key,
      text: event.text,
      payload_json:
        typeof event.payload_json === 'object' && event.payload_json !== null
          ? (event.payload_json as Record<string, unknown>)
          : undefined,
    })),
  }
}

export function extractTraceQuestionFromDetail(detail?: EvalTraceDetail | null): string {
  return parseQuestionInput(detail?.trace?.inputs_json)
}
