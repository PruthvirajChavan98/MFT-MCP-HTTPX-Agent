import { useCallback, useEffect, useRef, useState } from 'react'
import { API_BASE_URL, requestJson } from '../api/http'
import { streamSse } from '../api/sse'
import type { ChatMessage, CostEvent, ToolCallEvent } from '../types/chat'

const SESSION_KEY = 'nbfc_chat_session_id'
const messageKey = (sid: string) => `nbfc_chat_messages_${sid}`

interface FollowUpToken {
  index: number
  token: string
}

interface SessionInitResponse {
  session_id: string
  system_prompt: string
  model_name: string
  provider: string
}

function makeId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
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
    return parsed.filter(
      (item): item is ChatMessage =>
        item &&
        typeof item === 'object' &&
        typeof item.id === 'string' &&
        typeof item.role === 'string',
    )
  } catch {
    return []
  }
}

export function useChatStream() {
  const [sessionId, setSessionId] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [followUps, setFollowUps] = useState<string[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  // Fetch a new session from the backend
  const initNewSession = useCallback(async () => {
    try {
      const data = await requestJson<SessionInitResponse>({
        method: 'POST',
        path: '/agent/sessions/init', // Adjust prefix if your router is mounted differently
      })
      const sid = data.session_id
      localStorage.setItem(SESSION_KEY, sid)
      setSessionId(sid)
      setMessages([])
      setFollowUps([])
      setError('')
    } catch (err) {
      console.error('Failed to initialize session:', err)
      setError('Failed to initialize chat session')
    }
  }, [])

  // Initialize session on mount
  useEffect(() => {
    const existing = localStorage.getItem(SESSION_KEY)
    if (existing) {
      setSessionId(existing)
      setMessages(safeParseMessages(localStorage.getItem(messageKey(existing))))
    } else {
      initNewSession()
    }
  }, [initNewSession])

  // Persist messages whenever they change
  useEffect(() => {
    if (!sessionId) return
    localStorage.setItem(messageKey(sessionId), JSON.stringify(messages.slice(-120)))
  }, [messages, sessionId])

  const patchAssistant = useCallback((mutator: (last: ChatMessage) => ChatMessage) => {
    setMessages((prev) => {
      if (!prev.length) return prev
      const idx = prev.length - 1
      const last = prev[idx]
      if (last.role !== 'assistant') return prev
      const next = [...prev]
      next[idx] = mutator(last)
      return next
    })
  }, [])

  const appendAssistant = useCallback(
    (field: 'content' | 'reasoning', chunk: string) => {
      patchAssistant((last) => ({ ...last, [field]: `${last[field]}${chunk}` }))
    },
    [patchAssistant],
  )

  const fetchFollowUps = useCallback(
    async (question: string) => {
      if (!sessionId) return
      const chunks = new Map<number, string>()
      try {
        await streamSse(
          `${API_BASE_URL}/agent/follow-up-stream`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, question }),
          },
          {
            onEvent: (eventName, data, parsed) => {
              if (eventName !== 'token') return
              const token = parsed as FollowUpToken | undefined
              if (token && typeof token.index === 'number' && typeof token.token === 'string') {
                chunks.set(token.index, `${chunks.get(token.index) ?? ''}${token.token}`)
              } else if (typeof data === 'string' && data.trim()) {
                chunks.set(chunks.size, data.trim())
              }
            },
          },
        )
        const ordered = [...chunks.entries()]
          .sort((a, b) => a[0] - b[0])
          .map(([, v]) => v.trim())
          .filter(Boolean)
        setFollowUps(ordered.slice(0, 5))
      } catch {
        // follow-up errors are non-critical
      }
    },
    [sessionId],
  )

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || isStreaming || !sessionId) return

      setError('')
      setFollowUps([])

      const userMsg: ChatMessage = {
        id: makeId('msg'),
        role: 'user',
        content: trimmed,
        reasoning: '',
        timestamp: Date.now(),
        status: 'done',
        toolCalls: [],
        cost: null,
        router: null,
      }

      setMessages((prev) => [...prev, userMsg, createAssistantPlaceholder()])

      const abort = new AbortController()
      abortRef.current = abort
      setIsStreaming(true)

      let sawToken = false

      try {
        await streamSse(
          `${API_BASE_URL}/agent/stream`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, question: trimmed }),
            signal: abort.signal,
          },
          {
            onOpen: (res) => {
              if (!res.ok) setError(`Stream start failed: ${res.status}`)
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
                  if (payload?.name) {
                    patchAssistant((last) => ({
                      ...last,
                      toolCalls: [...last.toolCalls, payload],
                    }))
                  }
                  break
                }
                case 'cost': {
                  const payload = parsed as CostEvent | undefined
                  if (payload) patchAssistant((last) => ({ ...last, cost: payload }))
                  break
                }
                case 'router':
                  if (parsed && typeof parsed === 'object') {
                    patchAssistant((last) => ({
                      ...last,
                      router: parsed as Record<string, unknown>,
                    }))
                  }
                  break
                case 'error':
                  patchAssistant((last) => ({
                    ...last,
                    status: 'error',
                    content:
                      last.content || (typeof data === 'string' && data ? data : 'Stream error'),
                  }))
                  setError(typeof data === 'string' && data ? data : 'Stream error')
                  break
                case 'done':
                  patchAssistant((last) => ({ ...last, status: 'done' }))
                  break
              }
            },
          },
        )

        patchAssistant((last) => ({
          ...last,
          status: last.status === 'error' ? 'error' : 'done',
        }))

        if (!sawToken) {
          const fallback = await requestJson<{ response: string }>({
            method: 'POST',
            path: '/agent/query',
            body: { session_id: sessionId, question: trimmed },
          })
          patchAssistant((last) => ({
            ...last,
            content: fallback.response,
            status: 'done',
          }))
        }

        await fetchFollowUps(trimmed)
      } catch (raw) {
        const err = raw instanceof Error ? raw : new Error('Unknown stream failure')
        if (err.name === 'AbortError') {
          patchAssistant((last) => ({ ...last, status: 'done' }))
        } else {
          patchAssistant((last) => ({ ...last, status: 'error' }))
          setError(err.message)
        }
      } finally {
        setIsStreaming(false)
        abortRef.current = null
      }
    },
    [sessionId, isStreaming, appendAssistant, patchAssistant, fetchFollowUps],
  )

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const clearConversation = useCallback(() => {
    if (isStreaming) stopGeneration()
    // Fetching a new session instead of just clearing local state ensures
    // the backend memory is correctly reset for the user as well.
    initNewSession()
  }, [isStreaming, stopGeneration, initNewSession])

  return {
    sessionId,
    messages,
    followUps,
    isStreaming,
    error,
    sendMessage,
    stopGeneration,
    clearConversation,
  }
}
