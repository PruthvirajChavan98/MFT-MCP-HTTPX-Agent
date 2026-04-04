import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Conversations } from './Conversations'
import { resolveSelectedSession } from '@features/admin/hooks/useConversationQueries'
import type { ChatMessage } from '@shared/types/chat'
import type { SessionListItem } from '@features/admin/api/admin'

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

const SESSION_LIST_PAGE = {
  items: [
    {
      session_id: 'session-1',
      started_at: '2026-04-04T14:56:32Z',
      model: 'openai/gpt-oss-120b',
      provider: 'groq',
      message_count: 5,
      first_question: 'How do I download my welcome letter?',
    },
    {
      session_id: 'session-2',
      started_at: '2026-04-04T13:00:00Z',
      model: 'openai/gpt-oss-120b',
      provider: 'groq',
      message_count: 2,
      first_question: 'hi',
    },
  ],
  count: 2,
  limit: 80,
  next_cursor: null,
}

const SESSION_MESSAGES: ChatMessage[] = [
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
      { name: 'generate_otp', tool_call_id: 'tool-1', output: '{"status":"OTP Sent"}' },
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
]

const SESSION_COST = {
  session_id: 'session-1',
  total_cost: 0,
  total_requests: 5,
  total_tokens: 28792,
}

function createQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

function renderConversations(initialUrl = '/admin/conversations?sessionId=session-1') {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[initialUrl]}>
        <Conversations />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function setupDefaultMocks() {
  fetchConversationsPageMock.mockResolvedValue(SESSION_LIST_PAGE)
  fetchEvalSessionsMock.mockResolvedValue([])
  fetchSessionTracesMock.mockResolvedValue(SESSION_MESSAGES)
  fetchSessionCostMock.mockResolvedValue(SESSION_COST)
  useEvalStatusMock.mockReset()
}

describe('Conversations — URL-driven selection', () => {
  beforeEach(setupDefaultMocks)
  afterEach(() => vi.clearAllMocks())

  it('hydrates sessionId from URL and renders transcript without flicker', async () => {
    renderConversations('/admin/conversations?sessionId=session-1')

    expect(await screen.findByText('Transcript for')).toBeInTheDocument()
    expect(await screen.findByText('Hi again!')).toBeInTheDocument()
    expect(fetchSessionTracesMock).toHaveBeenCalledWith('admin-key', 'session-1')
  })

  it('auto-selects first session when no sessionId in URL', async () => {
    renderConversations('/admin/conversations')

    await waitFor(() => {
      expect(fetchSessionTracesMock).toHaveBeenCalledWith('admin-key', 'session-1')
    })
  })

  it('does not re-auto-select when search changes with an existing selection', async () => {
    renderConversations('/admin/conversations?sessionId=session-2')

    await waitFor(() => {
      expect(fetchSessionTracesMock).toHaveBeenCalledWith('admin-key', 'session-2')
    })
    // Should NOT have fetched session-1 (auto-select should not fire)
    expect(fetchSessionTracesMock).not.toHaveBeenCalledWith('admin-key', 'session-1')
  })

  it('preserves transcript when selected session is not in search results', async () => {
    fetchConversationsPageMock.mockResolvedValue({
      items: [SESSION_LIST_PAGE.items[1]],
      count: 1,
      limit: 80,
      next_cursor: null,
    })

    renderConversations('/admin/conversations?sessionId=session-1&search=hi')

    await waitFor(() => {
      expect(fetchSessionTracesMock).toHaveBeenCalledWith('admin-key', 'session-1')
    })

    expect(await screen.findByText('Not in current search')).toBeInTheDocument()
  })

  it('renders tool calls and reasoning in replay without eval polling', async () => {
    renderConversations('/admin/conversations?sessionId=session-1')

    const hiElements = await screen.findAllByText('Hi again!')
    expect(hiElements.length).toBeGreaterThanOrEqual(1)

    // Eval polling should NOT fire for transcript replays
    await waitFor(() => {
      expect(useEvalStatusMock).not.toHaveBeenCalled()
    })

    // Follow-ups should be non-interactive in replay
    expect(
      screen.queryByRole('button', { name: 'Can I resend the OTP now?' }),
    ).not.toBeInTheDocument()
    const followUps = screen.getAllByText('Can I resend the OTP now?')
    expect(followUps.length).toBeGreaterThanOrEqual(1)

    // Trace link should exist
    const traceLinks = screen.getAllByRole('link', { name: /view trace/i })
    expect(traceLinks.length).toBeGreaterThanOrEqual(1)
    expect(traceLinks[0]).toHaveAttribute('href', '/admin/traces?traceId=trace-1')
  })
})

describe('resolveSelectedSession — type safety', () => {
  const conversations: SessionListItem[] = [
    {
      session_id: 'session-1',
      started_at: '2026-04-04T14:56:32Z',
      model: 'openai/gpt-oss-120b',
      provider: 'groq',
      message_count: 5,
      first_question: 'How do I download my welcome letter?',
    },
  ]

  it('returns null when sessionId is null', () => {
    expect(resolveSelectedSession(null, conversations, [])).toBeNull()
  })

  it('returns full when session is in the list', () => {
    const result = resolveSelectedSession('session-1', conversations, [])
    expect(result).toMatchObject({ kind: 'full' })
    expect(result?.data.session_id).toBe('session-1')
  })

  it('returns partial when session is not in the list but traces exist', () => {
    const result = resolveSelectedSession('session-missing', [], SESSION_MESSAGES)
    expect(result).toMatchObject({ kind: 'partial' })
    expect(result?.data.session_id).toBe('session-missing')
  })

  it('returns partial with minimal data when session has no traces', () => {
    const result = resolveSelectedSession('session-empty', [], [])
    expect(result).toMatchObject({ kind: 'partial' })
    expect(result?.data.session_id).toBe('session-empty')
    expect(result?.data.model).toBeUndefined()
  })
})
