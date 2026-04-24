import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, waitForElementToBeRemoved } from '@testing-library/react'
import type { ReactElement } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatWidget } from './ChatWidget'

const { useChatStreamMock, useAvailableModelsMock, fetchSessionConfigMock, saveSessionConfigMock } =
  vi.hoisted(() => ({
  useChatStreamMock: vi.fn(),
  useAvailableModelsMock: vi.fn(),
  fetchSessionConfigMock: vi.fn(),
  saveSessionConfigMock: vi.fn(),
}))

vi.mock('@features/chat/hooks/useChatStream', () => ({
  useChatStream: useChatStreamMock,
}))

vi.mock('@shared/hooks/useModels', () => ({
  useAvailableModels: useAvailableModelsMock,
}))

vi.mock('@shared/api/sessions', () => ({
  fetchSessionConfig: fetchSessionConfigMock,
  saveSessionConfig: saveSessionConfigMock,
}))

function renderWithQueryClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  useChatStreamMock.mockReset()
  useAvailableModelsMock.mockReset()
  fetchSessionConfigMock.mockReset()
  saveSessionConfigMock.mockReset()
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: vi.fn(),
  })
})

afterEach(() => {
  cleanup()
})

describe('ChatWidget', () => {
  it('exposes a stable landing spotlight target on the closed launcher', () => {
    useChatStreamMock.mockReturnValue({
      sessionId: 'sid_test',
      messages: [],
      isStreaming: false,
      error: '',
      sendMessage: vi.fn(),
      stopGeneration: vi.fn(),
      clearConversation: vi.fn(),
    })

    render(<ChatWidget />)

    expect(screen.getByRole('button', { name: /open chat/i })).toHaveAttribute(
      'data-highlight-id',
      'landing-chat-launcher',
    )
  })

  it('renders assistant follow-up chips only once inside the message list', () => {
    useChatStreamMock.mockReturnValue({
      sessionId: 'sid_test',
      messages: [
        {
          id: 'msg_1',
          role: 'assistant',
          content: 'Here are some options.',
          reasoning: '',
          timestamp: Date.now(),
          status: 'done',
          toolCalls: [],
          cost: null,
          router: null,
          traceId: undefined,
          followUps: ['Can I view my repayment schedule?'],
        },
      ],
      isStreaming: false,
      error: '',
      sendMessage: vi.fn(),
      stopGeneration: vi.fn(),
      clearConversation: vi.fn(),
    })

    render(<ChatWidget />)

    fireEvent.click(screen.getByRole('button', { name: /open chat/i }))

    expect(screen.getAllByRole('button', { name: 'Can I view my repayment schedule?' })).toHaveLength(1)
  })

  it('renders model display names and keeps reasoning effort visible in settings', async () => {
    useChatStreamMock.mockReturnValue({
      sessionId: 'sid_test',
      messages: [],
      isStreaming: false,
      error: '',
      sendMessage: vi.fn(),
      stopGeneration: vi.fn(),
      clearConversation: vi.fn(),
    })
    useAvailableModelsMock.mockReturnValue({
      availableModels: [
        {
          id: 'openai/gpt-oss-120b',
          name: 'GPT OSS 120B',
          display_name: '🧠🛠️ GPT OSS 120B',
          supports_reasoning_effort: false,
          supports_tools: true,
        },
      ],
      isLoading: false,
    })
    fetchSessionConfigMock.mockResolvedValue({
      session_id: 'sid_test',
      provider: 'groq',
      model_name: 'openai/gpt-oss-120b',
      reasoning_effort: 'medium',
      system_prompt: 'Be helpful',
    })

    renderWithQueryClient(<ChatWidget />)

    fireEvent.click(screen.getByRole('button', { name: /open chat/i }))
    fireEvent.click(screen.getAllByTitle('Configure session')[0])

    expect(await screen.findByRole('option', { name: '🧠🛠️ GPT OSS 120B' })).toBeInTheDocument()
    expect(screen.getByText('Reasoning Effort')).toBeInTheDocument()
    expect(
      screen.getByText('Visible for all models; unsupported models ignore the saved setting.'),
    ).toBeInTheDocument()
  })

  it('blocks OpenRouter save until the session already has a key or the user enters one', async () => {
    useChatStreamMock.mockReturnValue({
      sessionId: 'sid_test',
      messages: [],
      isStreaming: false,
      error: '',
      sendMessage: vi.fn(),
      stopGeneration: vi.fn(),
      clearConversation: vi.fn(),
    })
    useAvailableModelsMock.mockReturnValue({
      availableModels: [
        {
          id: 'openai/o3-mini',
          name: 'o3-mini',
          display_name: '🧠 OpenAI o3-mini',
          supports_reasoning_effort: true,
          supports_tools: true,
        },
      ],
      isLoading: false,
    })
    fetchSessionConfigMock.mockResolvedValue({
      session_id: 'sid_test',
      provider: 'openrouter',
      model_name: 'openai/o3-mini',
      reasoning_effort: 'medium',
      system_prompt: 'Be helpful',
      has_openrouter_key: false,
    })

    renderWithQueryClient(<ChatWidget />)

    fireEvent.click(screen.getByRole('button', { name: /open chat/i }))
    fireEvent.click(screen.getAllByTitle('Configure session')[0])

    const saveButton = await screen.findByRole('button', { name: /save & apply/i })
    expect(saveButton).toBeDisabled()
    expect(
      screen.getByText('OpenRouter sessions require a key. Enter one now to save and apply this model.'),
    ).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText('Enter openrouter API Key'), {
      target: { value: 'sk-or-user' },
    })

    await waitFor(() => {
      expect(saveButton).toBeEnabled()
    })
  })

  it('allows NVIDIA save when the session already has a saved key', async () => {
    useChatStreamMock.mockReturnValue({
      sessionId: 'sid_test',
      messages: [],
      isStreaming: false,
      error: '',
      sendMessage: vi.fn(),
      stopGeneration: vi.fn(),
      clearConversation: vi.fn(),
    })
    useAvailableModelsMock.mockReturnValue({
      availableModels: [
        {
          id: 'nvidia/meta/llama-3.1-70b-instruct',
          name: 'Llama 3.1 70B Instruct',
          display_name: '💬 Llama 3.1 70B Instruct',
          supports_reasoning_effort: false,
          supports_tools: false,
        },
      ],
      isLoading: false,
    })
    fetchSessionConfigMock.mockResolvedValue({
      session_id: 'sid_test',
      provider: 'nvidia',
      model_name: 'nvidia/meta/llama-3.1-70b-instruct',
      reasoning_effort: 'medium',
      system_prompt: 'Be helpful',
      has_nvidia_key: true,
    })

    renderWithQueryClient(<ChatWidget />)

    fireEvent.click(screen.getByRole('button', { name: /open chat/i }))
    fireEvent.click(screen.getAllByTitle('Configure session')[0])

    await waitForElementToBeRemoved(() => screen.queryByText('Loading session config...'))
    expect(await screen.findByRole('button', { name: /save & apply/i })).toBeEnabled()
    expect(
      screen.getByText(
        'A saved NVIDIA key already exists for this session. Leave blank to keep it, or enter a new one to replace it.',
      ),
    ).toBeInTheDocument()
  })

  it('keeps Groq save optional when no session key exists', async () => {
    useChatStreamMock.mockReturnValue({
      sessionId: 'sid_test',
      messages: [],
      isStreaming: false,
      error: '',
      sendMessage: vi.fn(),
      stopGeneration: vi.fn(),
      clearConversation: vi.fn(),
    })
    useAvailableModelsMock.mockReturnValue({
      availableModels: [
        {
          id: 'openai/gpt-oss-120b',
          name: 'GPT OSS 120B',
          display_name: '🧠🛠️ GPT OSS 120B',
          supports_reasoning_effort: true,
          supports_tools: true,
        },
      ],
      isLoading: false,
    })
    fetchSessionConfigMock.mockResolvedValue({
      session_id: 'sid_test',
      provider: 'groq',
      model_name: 'openai/gpt-oss-120b',
      reasoning_effort: 'medium',
      system_prompt: 'Be helpful',
      has_groq_key: false,
    })

    renderWithQueryClient(<ChatWidget />)

    fireEvent.click(screen.getByRole('button', { name: /open chat/i }))
    fireEvent.click(screen.getAllByTitle('Configure session')[0])

    expect(await screen.findByRole('button', { name: /save & apply/i })).toBeEnabled()
    expect(
      screen.getByText('Groq BYOK is optional. Leave blank to use the server-managed Groq key.'),
    ).toBeInTheDocument()
  })
})
