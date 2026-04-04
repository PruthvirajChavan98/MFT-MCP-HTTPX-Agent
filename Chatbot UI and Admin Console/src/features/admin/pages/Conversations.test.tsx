import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Conversations } from './Conversations'
import type { ChatMessage } from '@shared/types/chat'

const {
  fetchConversationsPageMock,
  fetchEvalSessionsMock,
  fetchSessionCostMock,
  fetchSessionTracesMock,
  useEvalStatusMock,
} = vi.hoisted(() => ({
  fetchConversationsPageMock: vi.fn(),
  fetchEvalSessionsMock: vi.fn(),
  fetchSessionCostMock: vi.fn(),
  fetchSessionTracesMock: vi.fn(),
  useEvalStatusMock: vi.fn(),
}))

vi.mock('@features/admin/api/admin', () => ({
  fetchConversationsPage: (...args: unknown[]) => fetchConversationsPageMock(...args),
  fetchEvalSessions: (...args: unknown[]) => fetchEvalSessionsMock(...args),
  fetchSessionCost: (...args: unknown[]) => fetchSessionCostMock(...args),
  fetchSessionTraces: (...args: unknown[]) => fetchSessionTracesMock(...args),
}))

vi.mock('@features/admin/context/AdminContext', () => ({
  useAdminContext: () => ({
    adminKey: 'admin-key',
    setAdminKey: vi.fn(),
    openrouterKey: '',
    setOpenrouterKey: vi.fn(),
    nvidiaKey: '',
    setNvidiaKey: vi.fn(),
    groqKey: '',
    setGroqKey: vi.fn(),
  }),
}))

vi.mock('@features/chat/hooks/useEvalStatus', () => ({
  useEvalStatus: (...args: unknown[]) => useEvalStatusMock(...args),
}))

vi.mock('@components/ui/resizable', () => ({
  ResizablePanelGroup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ResizablePanel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ResizableHandle: () => <div data-testid="resize-handle" />,
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderConversations() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/admin/conversations?sessionId=session-1']}>
        <Conversations />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Conversations replay surface', () => {
  const sessionMessages: ChatMessage[] = [
    {
      id: 'user-1',
      role: 'user',
      content: 'login 9657052655',
      reasoning: '',
      timestamp: Date.now(),
      status: 'done',
    },
    {
      id: 'assistant-1',
      role: 'assistant',
      content: '<span style="color:#83f287">Hi again!</span>',
      reasoning: 'Used the saved transcript reasoning.',
      timestamp: Date.now(),
      status: 'done',
      traceId: 'trace-1',
      toolCalls: [
        {
          name: 'generate_otp',
          tool_call_id: 'tool-1',
          output: '{"status":"OTP Sent"}',
        },
      ],
      followUps: ['Can I resend the OTP now?'],
      evalStatus: {
        status: 'unavailable',
        reason: 'sampled_out',
        passed: undefined,
        failed: undefined,
        shadowJudge: undefined,
      },
    },
    {
      id: 'assistant-2',
      role: 'assistant',
      content: 'Fallback assistant message',
      reasoning: '',
      timestamp: Date.now(),
      status: 'done',
      evalStatus: {
        status: 'complete',
        reason: undefined,
        passed: 1,
        failed: 0,
        shadowJudge: undefined,
      },
    },
  ]

  beforeEach(() => {
    fetchConversationsPageMock.mockResolvedValue({
      items: [
        {
          session_id: 'session-1',
          started_at: '2026-04-04T14:56:32Z',
          model: 'openai/gpt-oss-120b',
          provider: 'groq',
          message_count: 5,
          first_question: 'How do I download my welcome letter?',
        },
      ],
      count: 1,
      limit: 80,
      next_cursor: null,
    })
    fetchEvalSessionsMock.mockResolvedValue([])
    fetchSessionTracesMock.mockResolvedValue(sessionMessages)
    fetchSessionCostMock.mockResolvedValue({
      session_id: 'session-1',
      total_cost: 0,
      total_requests: 5,
      total_tokens: 24884,
    })
    useEvalStatusMock.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders replay messages without live eval polling and preserves reasoning/tool/html details', async () => {
    renderConversations()

    expect(await screen.findByText('Transcript for')).toBeInTheDocument()
    expect(await screen.findByText('Hi again!')).toBeInTheDocument()

    await waitFor(() => {
      expect(useEvalStatusMock).not.toHaveBeenCalled()
    })

    const styledText = screen.getByText('Hi again!') as HTMLElement
    expect(styledText.style.color).toBe('rgb(131, 242, 135)')
    expect(screen.getByText('Eval skipped')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Can I resend the OTP now?' })).not.toBeInTheDocument()
    expect(screen.getByText('Can I resend the OTP now?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /reasoning/i }))
    expect(screen.getByText('Used the saved transcript reasoning.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /raw tool calls/i }))
    expect(screen.getAllByText('generate_otp')).toHaveLength(2)
    expect(screen.getByText('tool-1')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /view trace/i })).toHaveAttribute(
      'href',
      '/admin/traces?traceId=trace-1',
    )
  })

  it('renders trace links only for messages with a real trace id', async () => {
    renderConversations()

    await screen.findByText('Fallback assistant message')
    expect(screen.getAllByRole('link', { name: /view trace/i })).toHaveLength(1)
  })
})
