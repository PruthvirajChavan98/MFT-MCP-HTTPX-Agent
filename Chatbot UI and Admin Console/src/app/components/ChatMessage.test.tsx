import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { ChatMessage } from './ChatMessage'
import type { ChatMessage as ChatMessageType } from '../../shared/types/chat'

afterEach(() => {
  cleanup()
})

function makeAssistant(overrides: Partial<ChatMessageType> = {}): ChatMessageType {
  return {
    id: 'msg_1',
    role: 'assistant',
    content: 'hello',
    reasoning: '',
    timestamp: Date.now(),
    status: 'done',
    toolCalls: [],
    cost: null,
    router: null,
    traceId: undefined,
    ...overrides,
  }
}

describe('ChatMessage trace affordance', () => {
  it('renders clickable View trace link when traceId is present', () => {
    render(<ChatMessage message={makeAssistant({ traceId: 'trace_123' })} />)

    const link = screen.getByRole('link', { name: /view trace/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/admin/traces?traceId=trace_123')
  })

  it('renders non-link trace unavailable text for failed stream without traceId', () => {
    render(<ChatMessage message={makeAssistant({ status: 'error', traceId: undefined })} />)

    expect(screen.queryByRole('link', { name: /view trace/i })).not.toBeInTheDocument()
    expect(screen.getByText('Trace unavailable for this failed stream')).toBeInTheDocument()
  })
})
