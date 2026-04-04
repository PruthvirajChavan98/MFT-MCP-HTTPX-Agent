import { useCallback, useEffect, useRef, useState } from 'react'
import { API_BASE_URL, requestJson } from '@shared/api/http'
import { streamSse } from '@shared/api/sse'
import { parseMaybeJson } from '@shared/lib/json'
import type { ChatMessage, CostEvent, ToolCallEvent } from '@shared/types/chat'

const SESSION_KEY = 'nbfc_chat_session_id'
const messageKey = (sid: string) => `nbfc_chat_messages_${sid}`

interface FollowUpsPayload {
  questions?: string[]
}

interface SessionInitResponse {
  session_id: string
  system_prompt: string
  model_name: string
  provider: string
}

interface ErrorEventPayload {
  message?: string
}

interface TraceEventPayload {
  trace_id?: string
}

function parseToolCallEvent(payload: unknown, data: string): ToolCallEvent | undefined {
  const rawCandidate =
    payload && typeof payload === 'object'
      ? payload
      : (parseMaybeJson(data) as Record<string, unknown> | undefined)

  if (!rawCandidate || typeof rawCandidate !== 'object') return undefined

  const candidate = rawCandidate as Record<string, unknown>

  const name = typeof candidate.name === 'string' ? candidate.name.trim() : ''
  const toolCallId =
    typeof candidate.tool_call_id === 'string' ? candidate.tool_call_id.trim() : ''
  const output =
    typeof candidate.output === 'string'
      ? candidate.output
      : candidate.output !== undefined
        ? JSON.stringify(candidate.output)
        : ''

  if (!name) return undefined

  return {
    name,
    tool_call_id: toolCallId || name,
    output,
  }
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
    traceId: undefined,
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

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || isStreaming || !sessionId) return

      setError('')

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
        traceId: undefined,
      }

      setMessages((prev) => [...prev, userMsg, createAssistantPlaceholder()])

      const abort = new AbortController()
      abortRef.current = abort
      setIsStreaming(true)

      let hadToken = false
      let hadError = false
      let hadDone = false
      let hadTrace = false

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
                  hadToken = true
                  appendAssistant('content', data)
                  break
                case 'reasoning':
                  appendAssistant('reasoning', data)
                  break
                case 'tool_call': {
                  const payload = parseToolCallEvent(parsed, data)
                  if (payload?.name) {
                    patchAssistant((last) => {
                      const isDupe = last.toolCalls.some(
                        (tc) => tc.tool_call_id === payload.tool_call_id,
                      )
                      if (isDupe) return last
                      return { ...last, toolCalls: [...last.toolCalls, payload] }
                    })
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
                case 'trace':
                  if (parsed && typeof parsed === 'object' && 'trace_id' in parsed) {
                    const payload = parsed as TraceEventPayload
                    if (!payload.trace_id?.trim()) break
                    hadTrace = true
                    patchAssistant((last) => ({
                      ...last,
                      traceId: payload.trace_id,
                    }))
                  }
                  break
                case 'error':
                  hadError = true
                  hadDone = true
                  {
                    const payload = parsed as ErrorEventPayload | undefined
                    const parsedMessage =
                      payload && typeof payload === 'object' && payload.message?.trim()
                        ? payload.message.trim()
                        : ''

                    const dataMessage = (() => {
                      if (typeof data !== 'string' || !data.trim()) return ''
                      const parsedData = parsed as { message?: string } | undefined
                      if (parsedData && typeof parsedData.message === 'string' && parsedData.message.trim()) {
                        return parsedData.message.trim()
                      }
                      return data
                    })()

                    const message =
                      parsedMessage ||
                      dataMessage ||
                      'Stream error'

                    patchAssistant((last) => ({
                      ...last,
                      status: 'error',
                      content: last.content || message,
                    }))
                    setError(message)
                  }
                  break
                case 'follow_ups': {
                  const payload = parsed as FollowUpsPayload | undefined
                  if (payload?.questions) {
                    const questions = payload.questions.slice(0, 5)
                    patchAssistant((last) => ({
                      ...last,
                      followUps: questions,
                      content: last.content.replace(/\n?FOLLOW_UPS:\s*\[.*?\]\s*$/s, '').trimEnd(),
                    }))
                  }
                  break
                }
                case 'done':
                  hadDone = true
                  patchAssistant((last) => ({ ...last, status: last.status === 'error' ? 'error' : 'done' }))
                  break
              }
            },
          },
        )

        if (!hadDone) {
          patchAssistant((last) => ({
            ...last,
            status: last.status === 'error' ? 'error' : 'done',
          }))
        }

        if (!hadToken && !hadError) {
          const streamContractError = 'Streaming completed without response tokens.'
          patchAssistant((last) => ({
            ...last,
            status: 'error',
            content: last.content || streamContractError,
          }))
          setError(streamContractError)
          hadError = true
        }

        if (!hadTrace && hadError) {
          patchAssistant((last) => ({
            ...last,
            status: 'error',
          }))
        }

      } catch (raw) {
        const err = raw instanceof Error ? raw : new Error('Unknown stream failure')
        if (err.name === 'AbortError') {
          patchAssistant((last) => ({ ...last, status: 'done' }))
        } else {
          patchAssistant((last) => ({
            ...last,
            status: 'error',
            content: last.content || err.message,
          }))
          setError(err.message)
        }
      } finally {
        setIsStreaming(false)
        abortRef.current = null
      }
    },
    [sessionId, isStreaming, appendAssistant, patchAssistant],
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
    isStreaming,
    error,
    sendMessage,
    stopGeneration,
    clearConversation,
  }
}
