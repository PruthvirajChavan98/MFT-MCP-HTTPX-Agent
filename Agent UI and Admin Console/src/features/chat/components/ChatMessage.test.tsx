import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatMessage } from './ChatMessage'
import type { ChatMessage as ChatMessageType } from '@shared/types/chat'
import type { EvalStatusResult } from '@features/chat/hooks/useEvalStatus'

const { useEvalStatusMock } = vi.hoisted(() => ({
  useEvalStatusMock: vi.fn<(traceId: string | undefined) => EvalStatusResult | null>(),
}))

vi.mock('@features/chat/hooks/useEvalStatus', () => ({
  useEvalStatus: useEvalStatusMock,
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

afterEach(() => {
  cleanup()
  useEvalStatusMock.mockReset()
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

  it('renders a raw tool calls toggle beside reasoning and shows tool payloads when expanded', () => {
    render(
      <ChatMessage
        message={makeAssistant({
          reasoning: 'model reasoning',
          toolCalls: [
            {
              name: 'search_knowledge_base',
              tool_call_id: 'tool_123',
              output: '{"answer":"Sure"}',
            },
          ],
        })}
      />,
    )

    const bubble = screen.getByTestId('assistant-bubble')
    const reasoningButton = within(bubble).getByRole('button', { name: /reasoning/i })
    const rawToolButton = within(bubble).getByRole('button', { name: /raw tool calls/i })
    expect(reasoningButton.compareDocumentPosition(rawToolButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(rawToolButton).toBeInTheDocument()

    fireEvent.click(rawToolButton)

    expect(within(bubble).getByText('search_knowledge_base')).toBeInTheDocument()
    expect(within(bubble).getByText('tool_123')).toBeInTheDocument()
    expect(within(bubble).getByText(/"answer": "Sure"/)).toBeInTheDocument()
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

  it('does not render a raw tool calls toggle when no tool calls exist', () => {
    render(<ChatMessage message={makeAssistant({ reasoning: 'model reasoning', toolCalls: [] })} />)

    expect(screen.queryByRole('button', { name: /raw tool calls/i })).not.toBeInTheDocument()
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

describe('ChatMessage eval badge', () => {
  it('shows no eval badge when evalStatus is null', () => {
    useEvalStatusMock.mockReturnValue(null)

    render(<ChatMessage message={makeAssistant()} />)

    expect(screen.queryByText('Evaluating...')).not.toBeInTheDocument()
    expect(screen.queryByText(/Eval passed/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Eval:/)).not.toBeInTheDocument()
  })

  it('shows "Evaluating..." when status is pending', () => {
    useEvalStatusMock.mockReturnValue({
      status: 'pending',
      passed: undefined,
      failed: undefined,
      shadowJudge: undefined,
    })

    render(<ChatMessage message={makeAssistant({ traceId: 'trace-1' })} />)

    expect(screen.getByText('Evaluating...')).toBeInTheDocument()
  })

  it('shows "Eval passed" when complete with 0 failures', () => {
    useEvalStatusMock.mockReturnValue({
      status: 'complete',
      passed: 3,
      failed: 0,
      shadowJudge: undefined,
    })

    render(<ChatMessage message={makeAssistant({ traceId: 'trace-2' })} />)

    expect(screen.getByText('Eval passed')).toBeInTheDocument()
    expect(screen.queryByText('Evaluating...')).not.toBeInTheDocument()
  })

  it('shows "Eval: X/Y passed" when complete with failures', () => {
    useEvalStatusMock.mockReturnValue({
      status: 'complete',
      passed: 2,
      failed: 1,
      reason: undefined,
      shadowJudge: undefined,
    })

    render(<ChatMessage message={makeAssistant({ traceId: 'trace-3' })} />)

    expect(screen.getByText('Eval: 2/3 passed')).toBeInTheDocument()
  })

  it('hides eval badge when status is not_found', () => {
    useEvalStatusMock.mockReturnValue({
      status: 'not_found',
      passed: undefined,
      failed: undefined,
      reason: undefined,
      shadowJudge: undefined,
    })

    render(<ChatMessage message={makeAssistant({ traceId: 'trace-nf' })} />)

    expect(screen.queryByText('Evaluating...')).not.toBeInTheDocument()
    expect(screen.queryByText(/Eval passed/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Eval:/)).not.toBeInTheDocument()
  })

  it('does not render eval badge for user messages', () => {
    useEvalStatusMock.mockReturnValue({
      status: 'complete',
      passed: 1,
      failed: 0,
      reason: undefined,
      shadowJudge: undefined,
    })

    render(<ChatMessage message={makeUser({ traceId: 'trace-u' })} />)

    expect(screen.queryByText('Eval passed')).not.toBeInTheDocument()
  })

  it('shows "Eval skipped" when unavailable because the trace was sampled out', () => {
    useEvalStatusMock.mockReturnValue({
      status: 'unavailable',
      reason: 'sampled_out',
      passed: undefined,
      failed: undefined,
      shadowJudge: undefined,
    })

    render(<ChatMessage message={makeAssistant({ traceId: 'trace-sampled' })} />)

    expect(screen.getByText('Eval skipped')).toBeInTheDocument()
    expect(screen.queryByText('Evaluating...')).not.toBeInTheDocument()
  })

  it('shows "Eval timed out" when polling exhausts locally', () => {
    useEvalStatusMock.mockReturnValue({
      status: 'unavailable',
      reason: 'timed_out',
      passed: undefined,
      failed: undefined,
      shadowJudge: undefined,
    })

    render(<ChatMessage message={makeAssistant({ traceId: 'trace-timeout' })} />)

    expect(screen.getByText('Eval timed out')).toBeInTheDocument()
  })

  it('shows "Eval unavailable" for other unavailable terminal states', () => {
    useEvalStatusMock.mockReturnValue({
      status: 'unavailable',
      reason: 'failed',
      passed: undefined,
      failed: undefined,
      shadowJudge: undefined,
    })

    render(<ChatMessage message={makeAssistant({ traceId: 'trace-failed' })} />)

    expect(screen.getByText('Eval unavailable')).toBeInTheDocument()
  })
})
