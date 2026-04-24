import { describe, expect, it } from 'vitest'
import {
  extractInputTextFromTraceDetail,
  isBlockingDecision,
  mapGuardrailKpis,
  uniqueDecisionOptions,
} from './viewmodel'

describe('guardrails viewmodel', () => {
  it('maps KPI cards from summary, queue, and judge values', () => {
    const cards = mapGuardrailKpis({
      summary: {
        total_events: 10,
        deny_events: 3,
        allow_events: 7,
        deny_rate: 0.3,
        avg_risk_score: 0.45,
      },
      queue: {
        queue_key: 'q',
        depth: 4,
        dead_letter_queue_key: 'dlq',
        dead_letter_depth: 1,
        oldest_age_seconds: 12,
      },
      judge: {
        total_evals: 25,
        avg_helpfulness: 0.8,
        avg_faithfulness: 0.7,
        avg_policy_adherence: 0.92,
        recent_failures: [],
      },
    })

    expect(cards.find((card) => card.label === 'Deny Rate')?.value).toBe('30.0%')
    expect(cards.find((card) => card.label === 'Queue Depth')?.value).toBe('4')
    expect(cards.find((card) => card.label === 'Policy Adherence')?.value).toBe('92.0%')
  })

  it('builds unique decision filter options with all first', () => {
    const options = uniqueDecisionOptions([
      {
        event_time: '2026-01-01T00:00:00Z',
        session_id: 's1',
        risk_score: 0.9,
        risk_decision: 'block',
        reasons: ['unsafe_signal'],
      },
      {
        event_time: '2026-01-01T01:00:00Z',
        session_id: 's2',
        risk_score: 0.2,
        risk_decision: 'allow',
        reasons: ['safe'],
      },
      {
        event_time: '2026-01-01T02:00:00Z',
        session_id: 's3',
        risk_score: 0.1,
        risk_decision: 'allow',
        reasons: ['safe'],
      },
    ])

    expect(options[0]).toBe('all')
    expect(options).toContain('block')
    expect(options).toContain('allow')
  })

  it('extracts input text from trace detail payloads', () => {
    const input = extractInputTextFromTraceDetail({
      trace: {
        trace_id: 'trace-1',
        session_id: 'session-1',
        inputs_json: { input: 'test prompt' },
      },
      events: [],
      evals: [],
    })

    expect(input).toBe('test prompt')
    expect(isBlockingDecision('degraded_allow')).toBe(false)
    expect(isBlockingDecision('block')).toBe(true)
  })
})
