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

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  reasoning: string
  timestamp: number
  status: MessageStatus
  toolCalls: ToolCallEvent[]
  cost: CostEvent | null
  router: Record<string, unknown> | null
}
