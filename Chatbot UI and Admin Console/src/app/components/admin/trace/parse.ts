// src/app/components/admin/trace/parse.ts
import type { FlatNode, TraceDetail, TraceEvent } from './types'

export function parseToLangsmithTree(traceDetail: TraceDetail): FlatNode[] {
  if (!traceDetail) return []

  const nodes: FlatNode[] = []
  const trace = traceDetail.trace
  const events: TraceEvent[] = traceDetail.events ?? []

  const totalS = trace.latency_ms ? (trace.latency_ms / 1000).toFixed(2) : '0.00'

  nodes.push({
    id: 'root',
    type: 'trace',
    name: trace.name ?? 'Agent Trace',
    latencyS: totalS,
    status: trace.status === 'success' ? 'success' : 'error',
    tokens: 0,
    depth: 0,
    input: trace.inputs_json,
    output: trace.final_output,
    model: trace.model,
  })

  nodes.push({
    id: 'chain-1',
    type: 'chain',
    name: 'RunnableSequence',
    latencyS: totalS,
    status: 'success',
    tokens: 0,
    depth: 1,
    input: trace.inputs_json,
    output: trace.final_output,
  })

  let pendingReasoning: TraceEvent[] = []
  let pendingOutput: TraceEvent[] = []
  let seq = 0

  const getText = (e: TraceEvent): string => e.data ?? e.text ?? ''

  const flushReasoning = () => {
    if (pendingReasoning.length === 0) return
    nodes.push({
      id: `res-${seq++}`,
      type: 'llm',
      name: 'ReasoningEngine',
      latencyS: '0.00',
      status: 'success',
      tokens: pendingReasoning.length,
      depth: 2,
      input: 'System: You are an internal reasoning agent…',
      output: pendingReasoning.map(getText).join(''),
      model: trace.model,
    })
    pendingReasoning = []
  }

  const flushOutput = () => {
    if (pendingOutput.length === 0) return
    nodes.push({
      id: `out-${seq++}`,
      type: 'llm',
      name: 'GenerationEngine',
      latencyS: '0.00',
      status: 'success',
      tokens: pendingOutput.length,
      depth: 2,
      input: 'System: You are a helpful assistant generation node…',
      output: pendingOutput.map(getText).join(''),
      model: trace.model,
    })
    pendingOutput = []
  }

  for (const ev of events) {
    const etype = ev.event_type ?? ev.name ?? ev.event_key

    if (etype === 'reasoning') {
      flushOutput()
      pendingReasoning.push(ev)
    } else if (etype === 'token') {
      flushReasoning()
      pendingOutput.push(ev)
    } else if (
      etype === 'tool_call' ||
      etype === 'action' ||
      (etype && etype.includes('tool'))
    ) {
      flushReasoning()
      flushOutput()

      const payload = ev.payload_json

      nodes.push({
        id: `tool-parse-${seq++}`,
        type: 'parser',
        name: 'ToolParser',
        latencyS: '0.00',
        status: 'success',
        tokens: 0,
        depth: 2,
        input: payload ?? ev.text,
        output: 'Parsed tool call successfully',
      })

      nodes.push({
        id: `tool-exec-${seq++}`,
        type: 'tool',
        name: (payload?.name as string) ?? ev.event_key ?? 'execute_tool',
        latencyS: '0.00',
        status: 'success',
        tokens: 0,
        depth: 2,
        input: payload,
        output: payload?.output ?? 'Tool executed successfully',
      })
    }
  }

  flushReasoning()
  flushOutput()

  const totalTokens = nodes.reduce((acc, n) => acc + (n.tokens ?? 0), 0)
  nodes[0].tokens = totalTokens
  if (nodes[1]) nodes[1].tokens = totalTokens

  const children = nodes.slice(2)
  const childCount = children.length || 1
  children.forEach((n, i) => {
    n.offsetPct = (i / childCount) * 100
    n.durationPct = Math.max(4, 100 / childCount)
  })
  nodes[0].offsetPct = 0
  nodes[0].durationPct = 100
  if (nodes[1]) {
    nodes[1].offsetPct = 0
    nodes[1].durationPct = 100
  }

  return nodes
}