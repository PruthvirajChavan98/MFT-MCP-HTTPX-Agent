// src/app/components/admin/trace/types.ts
export type AggNodeType = 'trace' | 'chain' | 'llm' | 'parser' | 'tool'

export type NodeStatus = 'success' | 'error' | 'pending'

export interface FlatNode {
  id: string
  type: AggNodeType
  name: string
  latencyS: string
  status: NodeStatus
  tokens: number
  depth: number
  input?: unknown
  output?: unknown
  model?: string
  durationPct?: number
  offsetPct?: number
}

export interface TraceCost {
  total_cost: number
  currency: string
  model: string
  provider: string
  usage: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
    reasoning_tokens?: number
  }
}

export interface TraceEvent {
  event_type?: string
  name?: string
  event_key?: string
  text?: string
  data?: string
  payload_json?: Record<string, unknown>
}

export interface TraceDetail {
  trace: {
    name?: string
    latency_ms?: number
    status?: string
    inputs_json?: unknown
    final_output?: unknown
    model?: string
  }
  events?: TraceEvent[]
  cost?: TraceCost
}