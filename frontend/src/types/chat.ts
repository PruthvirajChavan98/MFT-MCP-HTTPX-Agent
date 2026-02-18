export type ChatRole = 'user' | 'assistant'

export type MessageStatus = 'pending' | 'streaming' | 'done' | 'error'

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
  }
  model: string
  provider: string
  currency: string
}

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  reasoning: string
  toolCalls: ToolCallEvent[]
  cost: CostEvent | null
  router: Record<string, unknown> | null
  status: MessageStatus
  timestamp: number
}

export interface ChatSession {
  id: string
  label: string
  createdAt: number
  messageCount: number
}

export interface SessionCostSummary {
  totalCost: number
  totalTokens: number
  promptTokens: number
  completionTokens: number
  reasoningTokens: number
  requestCount: number
}
