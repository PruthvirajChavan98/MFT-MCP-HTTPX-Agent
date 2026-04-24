export interface ToolCallEvent {
  name: string
  output: string
  tool_call_id: string
}

export interface CostEvent {
  total_cost: number
  usage: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
    reasoning_tokens: number
    cached_tokens?: number
  }
  model: string
  provider: string
  currency: string
  cached?: boolean
}

export type MessageRole = 'user' | 'assistant'
export type MessageStatus = 'pending' | 'streaming' | 'done' | 'error'

export interface EvalShadowJudge {
  helpfulness: number
  faithfulness: number
  policy_adherence: number
}

export type EvalStatusReason =
  | 'queued'
  | 'disabled'
  | 'sampled_out'
  | 'worker_backlog'
  | 'failed'
  | 'timed_out'

export interface EvalStatus {
  status: 'pending' | 'complete' | 'not_found' | 'unavailable'
  reason?: EvalStatusReason
  passed?: number
  failed?: number
  shadowJudge?: EvalShadowJudge | null
}

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  reasoning: string
  timestamp: number
  status: MessageStatus
  toolCalls?: ToolCallEvent[]
  cost?: CostEvent | null
  router?: Record<string, unknown> | null
  traceId?: string
  followUps?: string[]
  provider?: string
  model?: string
  totalTokens?: number
  evalStatus?: EvalStatus
}
