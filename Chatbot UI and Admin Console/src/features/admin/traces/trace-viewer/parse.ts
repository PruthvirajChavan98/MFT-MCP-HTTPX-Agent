import type { FlatNode, TraceDetail, TraceEvent } from './types'

type SegmentKind = 'llm' | 'parser' | 'tool'

type Segment = {
  key: string
  type: SegmentKind
  name: string
  tokens: number
  input?: unknown
  output?: unknown
  model?: string
  startMs?: number
  endMs?: number
}

function parseIsoMs(value?: string): number | undefined {
  if (!value) return undefined
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function formatLatency(ms?: number): string {
  if (!Number.isFinite(ms) || ms === undefined || ms <= 0) return '—'
  return (ms / 1000).toFixed(2)
}

function clampPct(value: number): number {
  return Math.max(0, Math.min(100, value))
}

function isToolEvent(eventType?: string): boolean {
  if (!eventType) return false
  return (
    eventType === 'tool_call' ||
    eventType === 'tool_start' ||
    eventType === 'tool_end' ||
    eventType === 'action' ||
    eventType.includes('tool')
  )
}

export function parseToLangsmithTree(traceDetail: TraceDetail): FlatNode[] {
  if (!traceDetail) return []

  const trace = traceDetail.trace
  const events = traceDetail.events ?? []
  const traceStartMs = parseIsoMs(trace.started_at)
  const traceEndMs = parseIsoMs(trace.ended_at)
  const totalLatencyLabel =
    trace.latency_ms !== undefined && trace.latency_ms !== null ? formatLatency(trace.latency_ms) : '—'

  const nodes: FlatNode[] = [
    {
      id: 'root',
      type: 'trace',
      name: trace.name ?? 'Agent Trace',
      latencyS: totalLatencyLabel,
      status: trace.status === 'success' ? 'success' : 'error',
      tokens: 0,
      depth: 0,
      input: trace.inputs_json,
      output: trace.final_output,
      model: trace.model,
      offsetPct: 0,
      durationPct: 100,
    },
    {
      id: 'chain-1',
      type: 'chain',
      name: 'RunnableSequence',
      latencyS: totalLatencyLabel,
      status: 'success',
      tokens: 0,
      depth: 1,
      input: trace.inputs_json,
      output: trace.final_output,
      offsetPct: 0,
      durationPct: 100,
    },
  ]

  const segments: Segment[] = []
  let pendingReasoning: TraceEvent[] = []
  let pendingOutput: TraceEvent[] = []
  let pendingTool: TraceEvent[] = []
  let seq = 0

  const getText = (event: TraceEvent) => event.data ?? event.text ?? ''
  const getPayload = (event: TraceEvent) => event.payload_json
  const getEventMs = (event: TraceEvent) => parseIsoMs(event.ts)

  const flushReasoning = () => {
    if (!pendingReasoning.length) return
    segments.push({
      key: `res-${seq++}`,
      type: 'llm',
      name: 'ReasoningEngine',
      tokens: pendingReasoning.length,
      input: 'System: You are an internal reasoning agent…',
      output: pendingReasoning.map(getText).join(''),
      model: trace.model,
      startMs: getEventMs(pendingReasoning[0]),
      endMs: getEventMs(pendingReasoning[pendingReasoning.length - 1]),
    })
    pendingReasoning = []
  }

  const flushOutput = () => {
    if (!pendingOutput.length) return
    segments.push({
      key: `out-${seq++}`,
      type: 'llm',
      name: 'GenerationEngine',
      tokens: pendingOutput.length,
      input: 'System: You are a helpful assistant generation node…',
      output: pendingOutput.map(getText).join(''),
      model: trace.model,
      startMs: getEventMs(pendingOutput[0]),
      endMs: getEventMs(pendingOutput[pendingOutput.length - 1]),
    })
    pendingOutput = []
  }

  const flushTool = () => {
    if (!pendingTool.length) return
    const first = pendingTool[0]
    const last = pendingTool[pendingTool.length - 1]
    // Input is emitted on tool_start (first); output on tool_end (last).
    // Reading either field from the wrong event yields undefined and loses the arg.
    const firstPayload = getPayload(first) as Record<string, unknown> | undefined
    const lastPayload = getPayload(last) as Record<string, unknown> | undefined
    const parserStartMs = getEventMs(first)
    const executionStartEvent =
      pendingTool.find((event) => {
        const eventType = event.event_type ?? event.name ?? event.event_key
        return eventType === 'tool_start' || eventType === 'action' || eventType === 'tool_end'
      }) ?? first
    const executionStartMs = getEventMs(executionStartEvent)

    const toolInput = firstPayload?.input ?? lastPayload?.input ?? firstPayload ?? lastPayload
    const toolOutput =
      lastPayload?.output ?? firstPayload?.output ?? last.text ?? 'Tool executed successfully'
    const toolName =
      (firstPayload?.tool as string | undefined) ??
      (lastPayload?.tool as string | undefined) ??
      (firstPayload?.name as string | undefined) ??
      (lastPayload?.name as string | undefined) ??
      last.name ??
      last.event_key ??
      'execute_tool'

    segments.push({
      key: `tool-parse-${seq++}`,
      type: 'parser',
      name: 'ToolParser',
      tokens: 0,
      input: firstPayload ?? first.text,
      output: 'Parsed tool call successfully',
      startMs: parserStartMs,
      endMs:
        parserStartMs !== undefined &&
        executionStartMs !== undefined &&
        executionStartMs > parserStartMs
          ? executionStartMs
          : undefined,
    })

    segments.push({
      key: `tool-exec-${seq++}`,
      type: 'tool',
      name: toolName,
      tokens: 0,
      input: toolInput,
      output: toolOutput,
      startMs: executionStartMs,
      endMs: getEventMs(last),
    })

    pendingTool = []
  }

  for (const event of events) {
    const eventType = event.event_type ?? event.name ?? event.event_key

    if (eventType === 'reasoning' || eventType === 'reasoning_token') {
      flushTool()
      flushOutput()
      pendingReasoning.push(event)
      continue
    }

    if (eventType === 'token') {
      flushTool()
      flushReasoning()
      pendingOutput.push(event)
      continue
    }

    if (isToolEvent(eventType)) {
      flushReasoning()
      flushOutput()
      pendingTool.push(event)
      continue
    }

    flushTool()
  }

  flushReasoning()
  flushOutput()
  flushTool()

  const timedSegments = segments.filter((segment) => segment.startMs !== undefined)
  const timelineStartMs = traceStartMs ?? timedSegments[0]?.startMs
  const totalDurationMs =
    trace.latency_ms && trace.latency_ms > 0
      ? trace.latency_ms
      : timelineStartMs !== undefined && traceEndMs !== undefined && traceEndMs > timelineStartMs
        ? traceEndMs - timelineStartMs
        : undefined
  const timelineEndMs =
    traceEndMs ??
    (timelineStartMs !== undefined && totalDurationMs !== undefined
      ? timelineStartMs + totalDurationMs
      : undefined)

  const childNodes = segments.map<FlatNode>((segment, index) => {
    const nextTimedStart = segments
      .slice(index + 1)
      .map((item) => item.startMs)
      .find((value) => value !== undefined)

    const durationMs =
      segment.startMs !== undefined
        ? segment.endMs && segment.endMs > segment.startMs
          ? segment.endMs - segment.startMs
          : nextTimedStart && nextTimedStart > segment.startMs
            ? nextTimedStart - segment.startMs
            : timelineEndMs && timelineEndMs > segment.startMs
              ? timelineEndMs - segment.startMs
              : undefined
        : undefined

    const offsetPct =
      timelineStartMs !== undefined &&
      totalDurationMs !== undefined &&
      totalDurationMs > 0 &&
      segment.startMs !== undefined
        ? clampPct(((segment.startMs - timelineStartMs) / totalDurationMs) * 100)
        : undefined

    const durationPct =
      totalDurationMs !== undefined &&
      totalDurationMs > 0 &&
      durationMs !== undefined &&
      durationMs > 0
        ? clampPct((durationMs / totalDurationMs) * 100)
        : undefined

    return {
      id: segment.key,
      type: segment.type,
      name: segment.name,
      latencyS: formatLatency(durationMs),
      status: 'success',
      tokens: segment.tokens,
      depth: 2,
      input: segment.input,
      output: segment.output,
      model: segment.model,
      offsetPct,
      durationPct,
    }
  })

  nodes.push(...childNodes)

  const totalTokens = nodes.reduce((sum, node) => sum + (node.tokens ?? 0), 0)
  nodes[0].tokens = totalTokens
  nodes[1].tokens = totalTokens

  return nodes
}
