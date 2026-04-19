import { describe, expect, it } from 'vitest'
import { parseToLangsmithTree } from './parse'
import type { TraceDetail } from './types'

describe('parseToLangsmithTree', () => {
  it('derives child-node latencies from timestamped eval events', () => {
    const detail: TraceDetail = {
      trace: {
        name: 'trace-1',
        latency_ms: 2500,
        status: 'success',
        inputs_json: { question: 'What is my EMI?' },
        final_output: 'Here is your EMI plan.',
        model: 'openai/gpt-oss-120b',
      },
      events: [
        { event_type: 'reasoning', ts: '2026-04-03T10:00:00.000Z', text: 'step 1' },
        { event_type: 'reasoning', ts: '2026-04-03T10:00:00.400Z', text: 'step 2' },
        {
          event_type: 'tool_call',
          ts: '2026-04-03T10:00:00.500Z',
          payload_json: { tool: 'mock_fintech_knowledge_base', input: { query: 'emi' } },
        },
        {
          event_type: 'tool_start',
          ts: '2026-04-03T10:00:00.650Z',
          payload_json: { tool: 'mock_fintech_knowledge_base', input: { query: 'emi' } },
        },
        {
          event_type: 'tool_end',
          ts: '2026-04-03T10:00:01.250Z',
          payload_json: { tool: 'mock_fintech_knowledge_base', output: 'KB answer' },
        },
        { event_type: 'token', ts: '2026-04-03T10:00:01.400Z', text: 'Here is' },
        { event_type: 'token', ts: '2026-04-03T10:00:01.900Z', text: ' your EMI plan.' },
      ],
    }

    const nodes = parseToLangsmithTree(detail)

    expect(nodes[0]).toMatchObject({ latencyS: '2.50' })
    expect(nodes.find((node) => node.name === 'ReasoningEngine')).toMatchObject({
      latencyS: '0.40',
    })
    expect(nodes.find((node) => node.name === 'ToolParser')).toMatchObject({
      latencyS: '0.15',
    })
    expect(nodes.find((node) => node.name === 'mock_fintech_knowledge_base')).toMatchObject({
      latencyS: '0.60',
    })
    expect(nodes.find((node) => node.name === 'GenerationEngine')).toMatchObject({
      latencyS: '0.50',
    })

    const knownDurationNodes = nodes.filter((node) => node.durationPct !== undefined)
    expect(knownDurationNodes.length).toBeGreaterThan(2)
  })

  it('preserves tool input from tool_start when tool_end omits it', () => {
    // Regression: collector emits input only on tool_start; tool_end has {tool, tool_call_id, output}.
    // Previously flushTool read payload from the last event and lost the input.
    const detail: TraceDetail = {
      trace: {
        name: 'trace-tool-input',
        latency_ms: 500,
        status: 'success',
        final_output: 'done',
      },
      events: [
        {
          event_type: 'tool_start',
          ts: '2026-04-18T10:00:00.000Z',
          payload_json: { tool: 'select_loan', input: { loan_id: 'MOCK-TWL-8a613a' } },
        },
        {
          event_type: 'tool_end',
          ts: '2026-04-18T10:00:00.400Z',
          payload_json: { tool: 'select_loan', tool_call_id: 'call_abc', output: 'selected' },
        },
      ],
    }

    const nodes = parseToLangsmithTree(detail)
    const toolNode = nodes.find((node) => node.name === 'select_loan')
    expect(toolNode).toBeDefined()
    expect(toolNode?.input).toEqual({ loan_id: 'MOCK-TWL-8a613a' })
    expect(toolNode?.output).toBe('selected')
  })

  it('shows unavailable timing when child-node timestamps do not exist', () => {
    const detail: TraceDetail = {
      trace: {
        name: 'trace-legacy',
        latency_ms: 0,
        status: 'success',
        final_output: 'Legacy trace',
      },
      events: [
        { event_type: 'tool_call', text: 'tool requested' },
        { event_type: 'token', text: 'legacy output' },
      ],
    }

    const nodes = parseToLangsmithTree(detail)

    expect(nodes[0].latencyS).toBe('—')
    expect(nodes.filter((node) => node.depth >= 2).every((node) => node.latencyS === '—')).toBe(true)
    expect(nodes.filter((node) => node.depth >= 2).every((node) => node.durationPct === undefined)).toBe(
      true,
    )
  })
})
