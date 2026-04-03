import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatMessage } from './ChatMessage'
import type { ChatMessage as ChatMessageType } from '@shared/types/chat'

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

function makeUser(overrides: Partial<ChatMessageType> = {}): ChatMessageType {
  return {
    id: 'msg_user_1',
    role: 'user',
    content: 'hi',
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

describe('ChatMessage', () => {
  it('renders the reasoning toggle inside the assistant bubble before assistant content', () => {
    render(<ChatMessage message={makeAssistant({ content: 'hello', reasoning: 'model reasoning' })} />)

    const bubble = screen.getByTestId('assistant-bubble')
    const reasoningButton = within(bubble).getByRole('button', { name: /reasoning/i })
    const content = within(bubble).getByText('hello')

    expect(reasoningButton.compareDocumentPosition(content) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

    fireEvent.click(reasoningButton)
    expect(within(bubble).getByText('model reasoning')).toBeInTheDocument()
  })

  it('renders follow-up chips once on the assistant message and forwards clicks', () => {
    const onFollowUpClick = vi.fn()

    render(
      <ChatMessage
        message={makeAssistant({
          followUps: ['Can I view my repayment schedule?'],
        })}
        onFollowUpClick={onFollowUpClick}
      />,
    )

    const chip = screen.getByRole('button', { name: 'Can I view my repayment schedule?' })
    expect(chip).toBeInTheDocument()

    fireEvent.click(chip)
    expect(onFollowUpClick).toHaveBeenCalledWith('Can I view my repayment schedule?')
  })

  it('does not render follow-up chips for user messages', () => {
    render(
      <ChatMessage
        message={makeUser({
          followUps: ['Should stay hidden'],
        })}
      />,
    )

    expect(screen.queryByRole('button', { name: 'Should stay hidden' })).not.toBeInTheDocument()
  })

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
