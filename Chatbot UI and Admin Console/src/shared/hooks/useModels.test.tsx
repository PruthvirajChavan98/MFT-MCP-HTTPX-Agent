import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAvailableModels } from './useModels'

const { fetchModelsMock } = vi.hoisted(() => ({
  fetchModelsMock: vi.fn(),
}))

vi.mock('@features/admin/api/admin', () => ({
  fetchModels: fetchModelsMock,
}))

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

describe('useAvailableModels', () => {
  beforeEach(() => {
    fetchModelsMock.mockReset()
  })

  it('preserves capability metadata and auto-selects the first valid model', async () => {
    fetchModelsMock.mockResolvedValueOnce([
      {
        name: 'groq',
        models: [
          {
            id: 'openai/gpt-oss-120b',
            name: 'GPT OSS 120B',
            display_name: '🧠🛠️ GPT OSS 120B',
            provider: 'groq',
            is_reasoning_model: true,
            supports_reasoning_effort: true,
            supports_tools: true,
          },
        ],
      },
    ])

    const onModelChange = vi.fn()
    const wrapper = createWrapper()

    const { result } = renderHook(
      () => useAvailableModels('groq', 'missing-model', onModelChange),
      { wrapper },
    )

    await waitFor(() => {
      expect(result.current.availableModels).toHaveLength(1)
    })

    expect(result.current.availableModels[0].display_name).toBe('🧠🛠️ GPT OSS 120B')
    expect(result.current.availableModels[0].supports_tools).toBe(true)

    await waitFor(() => {
      expect(onModelChange).toHaveBeenCalledWith('openai/gpt-oss-120b')
    })
  })
})
