import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useChatStream } from './useChatStream'

const { streamSseMock, requestJsonMock } = vi.hoisted(() => ({
  streamSseMock: vi.fn(),
  requestJsonMock: vi.fn(),
}))

type StreamOnEvent = (eventName: string, data: string, parsed?: unknown) => void

vi.mock('@shared/api/http', () => ({
  API_BASE_URL: '/api',
  requestJson: requestJsonMock,
}))

vi.mock('@shared/api/sse', () => ({
  streamSse: streamSseMock,
}))

describe('useChatStream stream-only contract', () => {
  beforeEach(() => {
    streamSseMock.mockReset()
    requestJsonMock.mockReset()
    localStorage.clear()

    requestJsonMock.mockResolvedValue({
      session_id: 'sid_test',
      provider: 'groq',
      model_name: 'test-model',
      system_prompt: 'sys',
    })
  })

  async function initHook() {
    const hook = renderHook(() => useChatStream())

    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    return hook
  }

  it('uses /agent/stream only on token+trace+done and never calls /agent/query', async () => {
    streamSseMock.mockImplementation(async (url: string, _init: RequestInit, handlers: { onEvent: StreamOnEvent }) => {
      if (url.endsWith('/agent/stream')) {
        handlers.onEvent('token', 'hello ')
        handlers.onEvent('trace', JSON.stringify({ trace_id: 'trace_1' }), { trace_id: 'trace_1' })
        handlers.onEvent('done', JSON.stringify({ status: 'complete' }), { status: 'complete' })
      }
    })

    const hook = await initHook()

    await act(async () => {
      await hook.result.current.sendMessage('hi')
    })

    const streamCall = streamSseMock.mock.calls.find(([url]: [string]) => url.endsWith('/agent/stream'))
    expect(streamCall).toBeTruthy()
    expect(requestJsonMock.mock.calls.some((args) => args?.[0]?.path === '/agent/query')).toBe(false)

    const assistant = hook.result.current.messages.find((m) => m.role === 'assistant')
    expect(assistant?.traceId).toBe('trace_1')
    expect(assistant?.status).toBe('done')
  })

  it('keeps stream-only behavior on error+trace+done and preserves trace id', async () => {
    streamSseMock.mockImplementation(async (url: string, _init: RequestInit, handlers: { onEvent: StreamOnEvent }) => {
      if (url.endsWith('/agent/stream')) {
        handlers.onEvent('error', JSON.stringify({ message: 'backend stream failed' }), {
          message: 'backend stream failed',
        })
        handlers.onEvent('trace', JSON.stringify({ trace_id: 'trace_err' }), { trace_id: 'trace_err' })
        handlers.onEvent('done', JSON.stringify({ status: 'complete' }), { status: 'complete' })
      }
    })

    const hook = await initHook()

    await act(async () => {
      await hook.result.current.sendMessage('test error')
    })

    expect(requestJsonMock.mock.calls.some((args) => args?.[0]?.path === '/agent/query')).toBe(false)

    const assistant = hook.result.current.messages.find((m) => m.role === 'assistant')
    expect(assistant?.status).toBe('error')
    expect(assistant?.traceId).toBe('trace_err')
    expect(assistant?.content).toContain('backend stream failed')
  })

  it('marks response as stream-contract error when done arrives without token/error', async () => {
    streamSseMock.mockImplementation(async (url: string, _init: RequestInit, handlers: { onEvent: StreamOnEvent }) => {
      if (url.endsWith('/agent/stream')) {
        handlers.onEvent('done', JSON.stringify({ status: 'complete' }), { status: 'complete' })
      }
    })

    const hook = await initHook()

    await act(async () => {
      await hook.result.current.sendMessage('done-only')
    })

    expect(requestJsonMock.mock.calls.some((args) => args?.[0]?.path === '/agent/query')).toBe(false)

    const assistant = hook.result.current.messages.find((m) => m.role === 'assistant')
    expect(assistant?.status).toBe('error')
    expect(assistant?.content).toContain('Streaming completed without response tokens.')
    expect(hook.result.current.error).toContain('Streaming completed without response tokens.')
  })

  it('stores follow-ups on the active assistant message and strips trailing follow-up payload text', async () => {
    streamSseMock.mockImplementation(async (url: string, _init: RequestInit, handlers: { onEvent: StreamOnEvent }) => {
      if (url.endsWith('/agent/stream')) {
        handlers.onEvent(
          'token',
          'Here are some options.\nFOLLOW_UPS:["Can I view my repayment schedule?"]',
        )
        handlers.onEvent(
          'follow_ups',
          JSON.stringify({ questions: ['Can I view my repayment schedule?'] }),
          { questions: ['Can I view my repayment schedule?'] },
        )
        handlers.onEvent('done', JSON.stringify({ status: 'complete' }), { status: 'complete' })
      }
    })

    const hook = await initHook()

    await act(async () => {
      await hook.result.current.sendMessage('show options')
    })

    const assistant = hook.result.current.messages.find((m) => m.role === 'assistant')
    expect(assistant?.followUps).toEqual(['Can I view my repayment schedule?'])
    expect(assistant?.content).toBe('Here are some options.')
    expect('followUps' in (hook.result.current as unknown as Record<string, unknown>)).toBe(false)
  })
})
