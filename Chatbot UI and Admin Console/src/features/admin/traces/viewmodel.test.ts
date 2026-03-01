import { describe, expect, it } from 'vitest'
import {
  extractTraceQuestionFromDetail,
  getTraceInputPreview,
  mapTraceListRows,
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

  it('extracts question from trace detail inputs', () => {
    const question = extractTraceQuestionFromDetail({
      trace: {
        trace_id: 'trace-1',
        session_id: 'session-1',
        inputs_json: { question: 'Explain X' },
      },
      events: [],
      evals: [],
    })

    expect(question).toBe('Explain X')
  })
})
