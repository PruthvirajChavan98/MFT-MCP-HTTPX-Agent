import { createEffect, createSignal, onMount } from 'solid-js'
import { API_BASE_URL, requestJson } from '../../shared/api/http'
import { streamSse } from '../../shared/lib/sse'
import type { ChatMessage, CostEvent, ToolCallEvent } from '../../shared/types/chat'

const SESSION_KEY = 'nbfc_chat_session_id'
const messageKey = (sessionId: string) => `nbfc_chat_messages_${sessionId}`

interface FollowUpToken {
  index: number
  token: string
}

function makeId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function createSessionId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function createAssistantPlaceholder(): ChatMessage {
  return {
    id: makeId('msg'),
    role: 'assistant',
    content: '',
    reasoning: '',
    timestamp: Date.now(),
    status: 'streaming',
    toolCalls: [],
    cost: null,
    router: null,
  }
}

function safeParseMessages(raw: string | null): ChatMessage[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item): item is ChatMessage => {
      return item && typeof item === 'object' && typeof item.id === 'string' && typeof item.role === 'string'
    })
  } catch {
    return []
  }
}

export function useChatController() {
  const [sessionId, setSessionId] = createSignal('')
  const [messages, setMessages] = createSignal<ChatMessage[]>([])
  const [input, setInput] = createSignal('')
  const [followUps, setFollowUps] = createSignal<string[]>([])
  const [isStreaming, setIsStreaming] = createSignal(false)
  const [error, setError] = createSignal('')
  const [activeAbort, setActiveAbort] = createSignal<AbortController | null>(null)

  const persistMessages = () => {
    const sid = sessionId()
    if (!sid) return
    localStorage.setItem(messageKey(sid), JSON.stringify(messages().slice(-120)))
  }

  createEffect(() => {
    messages()
    persistMessages()
  })

  function patchAssistant(mutator: (last: ChatMessage) => ChatMessage): void {
    setMessages((prev) => {
      if (!prev.length) return prev
      const index = prev.length - 1
      const last = prev[index]
      if (last.role !== 'assistant') return prev
      const next = [...prev]
      next[index] = mutator(last)
      return next
    })
  }

  function appendAssistant(field: 'content' | 'reasoning', chunk: string): void {
    patchAssistant((last) => ({ ...last, [field]: `${last[field]}${chunk}` }))
  }

  async function fetchFollowUps(question: string): Promise<void> {
    const sid = sessionId()
    if (!sid) return

    const chunks = new Map<number, string>()

    await streamSse(
      `${API_BASE_URL}/agent/follow-up-stream`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sid, question }),
      },
      {
        onEvent: (eventName, data, parsed) => {
          if (eventName !== 'token') return
          const token = parsed as FollowUpToken | undefined
          if (token && typeof token.index === 'number' && typeof token.token === 'string') {
            chunks.set(token.index, `${chunks.get(token.index) ?? ''}${token.token}`)
          } else if (typeof data === 'string' && data.trim()) {
            const index = chunks.size
            chunks.set(index, data.trim())
          }
        },
      },
    )

    const ordered = [...chunks.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([, value]) => value.trim())
      .filter(Boolean)

    setFollowUps(ordered.slice(0, 5))
  }

  async function sendMessage(overrideText?: string): Promise<void> {
    const text = (overrideText ?? input()).trim()
    if (!text || isStreaming()) return

    const sid = sessionId()
    if (!sid) return

    setError('')
    setFollowUps([])

    const userMessage: ChatMessage = {
      id: makeId('msg'),
      role: 'user',
      content: text,
      reasoning: '',
      timestamp: Date.now(),
      status: 'done',
      toolCalls: [],
      cost: null,
      router: null,
    }

    setMessages((prev) => [...prev, userMessage, createAssistantPlaceholder()])
    setInput('')

    const abort = new AbortController()
    setActiveAbort(abort)
    setIsStreaming(true)

    let sawToken = false

    try {
      await streamSse(
        `${API_BASE_URL}/agent/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sid, question: text }),
          signal: abort.signal,
        },
        {
          onOpen: (response) => {
            if (!response.ok) {
              setError(`Stream start failed: ${response.status}`)
            }
          },
          onEvent: (eventName, data, parsed) => {
            switch (eventName) {
              case 'token':
                sawToken = true
                appendAssistant('content', data)
                break
              case 'reasoning':
                appendAssistant('reasoning', data)
                break
              case 'tool_call': {
                const payload = parsed as ToolCallEvent | undefined
                if (!payload || !payload.name) break
                patchAssistant((last) => ({ ...last, toolCalls: [...last.toolCalls, payload] }))
                break
              }
              case 'cost': {
                const payload = parsed as CostEvent | undefined
                if (!payload) break
                patchAssistant((last) => ({ ...last, cost: payload }))
                break
              }
              case 'router':
                if (parsed && typeof parsed === 'object') {
                  patchAssistant((last) => ({ ...last, router: parsed as Record<string, unknown> }))
                }
                break
              case 'error':
                patchAssistant((last) => ({
                  ...last,
                  status: 'error',
                  content: last.content || (typeof data === 'string' && data ? data : 'Stream error'),
                }))
                setError(typeof data === 'string' && data ? data : 'Stream error')
                break
              case 'done':
                patchAssistant((last) => ({ ...last, status: 'done' }))
                break
              default:
                break
            }
          },
        },
      )

      patchAssistant((last) => ({ ...last, status: last.status === 'error' ? 'error' : 'done' }))

      if (!sawToken) {
        const fallback = await requestJson<{ response: string }>({
          method: 'POST',
          path: '/agent/query',
          body: { session_id: sid, question: text },
        })
        patchAssistant((last) => ({ ...last, content: fallback.response, status: 'done' }))
      }

      await fetchFollowUps(text)
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Unknown stream failure')
      if (err.name === 'AbortError') {
        patchAssistant((last) => ({ ...last, status: 'done' }))
      } else {
        patchAssistant((last) => ({ ...last, status: 'error' }))
        setError(err.message)
      }
    } finally {
      setIsStreaming(false)
      setActiveAbort(null)
    }
  }

  function stopGeneration(): void {
    activeAbort()?.abort()
  }

  function clearConversation(): void {
    if (isStreaming()) {
      stopGeneration()
    }
    setMessages([])
    setFollowUps([])
    setError('')
  }

  onMount(() => {
    const existingSession = localStorage.getItem(SESSION_KEY)
    const sid = existingSession || createSessionId()

    if (!existingSession) {
      localStorage.setItem(SESSION_KEY, sid)
    }

    setSessionId(sid)
    setMessages(safeParseMessages(localStorage.getItem(messageKey(sid))))
  })

  return {
    sessionId,
    messages,
    input,
    setInput,
    followUps,
    isStreaming,
    error,
    sendMessage,
    stopGeneration,
    clearConversation,
  }
}
