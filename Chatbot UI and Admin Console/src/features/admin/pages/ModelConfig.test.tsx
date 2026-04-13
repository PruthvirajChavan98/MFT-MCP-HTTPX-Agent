import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactElement } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ModelConfig } from './ModelConfig'

const {
  fetchSessionConfigMock,
  saveSessionConfigMock,
  useAvailableModelsMock,
  useAdminContextMock,
} = vi.hoisted(() => ({
  fetchSessionConfigMock: vi.fn(),
  saveSessionConfigMock: vi.fn(),
  useAvailableModelsMock: vi.fn(),
  useAdminContextMock: vi.fn(),
}))

vi.mock('@features/admin/api/admin', () => ({
  fetchSessionConfig: fetchSessionConfigMock,
  saveSessionConfig: saveSessionConfigMock,
}))

vi.mock('../../../shared/hooks/useModels', () => ({
  useAvailableModels: useAvailableModelsMock,
}))

vi.mock('@features/admin/context/AdminContext', () => ({
  useAdminContext: useAdminContextMock,
}))

function renderWithQueryClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

function defaultAdminContext(overrides: Partial<ReturnType<typeof useAdminContextMock>> = {}) {
  return {
    openrouterKey: '',
    nvidiaKey: '',
    groqKey: '',
    setOpenrouterKey: vi.fn(),
    setNvidiaKey: vi.fn(),
    setGroqKey: vi.fn(),
    ...overrides,
  }
}

beforeEach(() => {
  fetchSessionConfigMock.mockReset()
  saveSessionConfigMock.mockReset()
  useAvailableModelsMock.mockReset()
  useAdminContextMock.mockReset()
  ;(globalThis as { ResizeObserver?: typeof ResizeObserver }).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver

  useAvailableModelsMock.mockReturnValue({
    availableModels: [
      {
        id: 'openai/o3-mini',
        name: 'o3-mini',
        display_name: '🧠 OpenAI o3-mini',
        supports_reasoning_effort: true,
        supports_tools: true,
        is_reasoning_model: true,
      },
    ],
    isLoading: false,
  })
  useAdminContextMock.mockReturnValue(defaultAdminContext())
})

afterEach(() => {
  cleanup()
})

async function loadSession(sessionId: string) {
  fireEvent.change(screen.getByPlaceholderText('Enter Session ID to override...'), {
    target: { value: sessionId },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Load Config' }))

  await waitFor(() => {
    expect(fetchSessionConfigMock).toHaveBeenCalledWith(sessionId)
  })
}

describe('ModelConfig', () => {
  it('blocks OpenRouter commits when there is no saved or newly provided key', async () => {
    fetchSessionConfigMock.mockResolvedValue({
      session_id: 'sid-openrouter',
      provider: 'openrouter',
      model_name: 'openai/o3-mini',
      reasoning_effort: 'medium',
      system_prompt: 'Be helpful',
      has_openrouter_key: false,
    })

    renderWithQueryClient(<ModelConfig />)
    await loadSession('sid-openrouter')

    expect(
      await screen.findByText(
        'OpenRouter requires an API key. Enter your key below to continue.',
      ),
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /commit to session/i })).toBeDisabled()
    })
  })

  it('allows OpenRouter commits when the session already has a saved key', async () => {
    fetchSessionConfigMock.mockResolvedValue({
      session_id: 'sid-openrouter',
      provider: 'openrouter',
      model_name: 'openai/o3-mini',
      reasoning_effort: 'medium',
      system_prompt: 'Be helpful',
      has_openrouter_key: true,
    })

    renderWithQueryClient(<ModelConfig />)
    await loadSession('sid-openrouter')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /commit to session/i })).toBeEnabled()
    })
  })

  it('allows NVIDIA commits when a new admin key is available', async () => {
    useAdminContextMock.mockReturnValue(defaultAdminContext({ nvidiaKey: 'nvapi-test' }))
    fetchSessionConfigMock.mockResolvedValue({
      session_id: 'sid-nvidia',
      provider: 'nvidia',
      model_name: 'nvidia/meta/llama-3.1-70b-instruct',
      reasoning_effort: 'medium',
      system_prompt: 'Be helpful',
      has_nvidia_key: false,
    })
    useAvailableModelsMock.mockReturnValue({
      availableModels: [
        {
          id: 'nvidia/meta/llama-3.1-70b-instruct',
          name: 'Llama 3.1 70B Instruct',
          display_name: '💬 Llama 3.1 70B Instruct',
          supports_reasoning_effort: false,
          supports_tools: false,
          is_reasoning_model: false,
        },
      ],
      isLoading: false,
    })

    renderWithQueryClient(<ModelConfig />)
    await loadSession('sid-nvidia')

    expect(
      await screen.findByText('NVIDIA key provided. It will be saved when you commit this session.'),
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /commit to session/i })).toBeEnabled()
    })
  })

  it('keeps Groq commits optional when no key is present', async () => {
    fetchSessionConfigMock.mockResolvedValue({
      session_id: 'sid-groq',
      provider: 'groq',
      model_name: 'openai/gpt-oss-120b',
      reasoning_effort: 'medium',
      system_prompt: 'Be helpful',
      has_groq_key: false,
    })
    useAvailableModelsMock.mockReturnValue({
      availableModels: [
        {
          id: 'openai/gpt-oss-120b',
          name: 'GPT OSS 120B',
          display_name: '🧠🛠️ GPT OSS 120B',
          supports_reasoning_effort: true,
          supports_tools: true,
          is_reasoning_model: true,
        },
      ],
      isLoading: false,
    })

    renderWithQueryClient(<ModelConfig />)
    await loadSession('sid-groq')

    expect(
      await screen.findByText(
        'Groq BYOK is optional. Without one, the server-managed Groq key is used.',
      ),
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /commit to session/i })).toBeEnabled()
    })
  })
})
