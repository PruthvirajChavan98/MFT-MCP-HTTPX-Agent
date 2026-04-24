import { describe, expect, it } from 'vitest'
import {
  getTraceInputPreview,
  mapTraceListRows,
  mapTraceDetailToViewer,
} from './viewmodel'

describe('traces viewmodel', () => {
  it('derives trace input previews from structured input payloads', () => {
    const preview = getTraceInputPreview({
      inputs_json: { question: 'What is the capital of France?' },
      final_output: 'Paris',
    })

    expect(preview).toBe('What is the capital of France?')
  })

  it('maps trace rows with status and conversation links', () => {
    const rows = mapTraceListRows([
      {
        trace_id: 'trace-1',
        session_id: 'session-1',
        model: 'deepseek-v3',
        inputs_json: { input: 'hello' },
        final_output: 'world',
        error: undefined,
      },
      {
        trace_id: 'trace-2',
        session_id: 'session-2',
        model: 'deepseek-v3',
        inputs_json: null,
        final_output: 'fallback output',
        error: 'timeout',
      },
    ])

    expect(rows[0]).toMatchObject({
      traceId: 'trace-1',
      status: 'success',
      inputPreview: 'hello',
      conversationHref: '/admin/conversations?sessionId=session-1',
    })
    expect(rows[1]).toMatchObject({
      traceId: 'trace-2',
      status: 'error',
      inputPreview: 'fallback output',
    })
  })

  it('preserves trace event timestamps for the viewer parser', () => {
    const detail = mapTraceDetailToViewer({
      trace: {
        trace_id: 'trace-1',
        session_id: 'session-1',
        started_at: '2026-04-03T10:00:00.000Z',
        ended_at: '2026-04-03T10:00:02.500Z',
        latency_ms: 2500,
      },
      events: [
        {
          event_key: 'evt-1',
          seq: 1,
          ts: '2026-04-03T10:00:01.000Z',
          event_type: 'token',
          text: 'hello',
        },
      ],
      evals: [],
    })

    expect(detail?.trace.started_at).toBe('2026-04-03T10:00:00.000Z')
    expect(detail?.trace.ended_at).toBe('2026-04-03T10:00:02.500Z')
    expect(detail?.events?.[0]).toMatchObject({
      seq: 1,
      ts: '2026-04-03T10:00:01.000Z',
      event_type: 'token',
    })
  })
})
