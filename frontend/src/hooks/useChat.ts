import { createEffect, createMemo, createSignal, on, onMount } from 'solid-js'
import type { ChatMessage, ChatSession, CostEvent, SessionCostSummary, ToolCallEvent } from '../types/chat'
import { parseMaybeJson } from '../lib/json'
import { streamSse } from '../lib/stream'

const STORAGE_SESSIONS = 'hfcl_chat_sessions'
const storageMessagesKey = (id: string) => `hfcl_chat_msgs_${id}`
const MAX_STORED_MESSAGES = 200
const MAX_STORED_FIELD_LEN = 2000

function generateId(): string {
  return `chat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function messageId(): string {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // QuotaExceededError — silently drop
  }
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) : s
}

function compactForStorage(msgs: ChatMessage[]): ChatMessage[] {
  return msgs.slice(-MAX_STORED_MESSAGES).map((m) => ({
    ...m,
    reasoning: truncate(m.reasoning, MAX_STORED_FIELD_LEN),
    toolCalls: m.toolCalls.map((tc) => ({ ...tc, output: truncate(tc.output, MAX_STORED_FIELD_LEN) })),
  }))
}

const emptyCost: SessionCostSummary = {
  totalCost: 0,
  totalTokens: 0,
  promptTokens: 0,
  completionTokens: 0,
  reasoningTokens: 0,
  requestCount: 0,
}

export function useChat() {
  const baseUrl = () => import.meta.env.VITE_API_BASE_URL ?? '/api'

  // ── session state ──
  const [sessions, setSessions] = createSignal<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = createSignal('')

  // ── conversation state ──
  const [messages, setMessages] = createSignal<ChatMessage[]>([])
  const [inputText, setInputText] = createSignal('')

  // ── streaming state ──
  const [isStreaming, setIsStreaming] = createSignal(false)
  const [activeController, setActiveController] = createSignal<AbortController | null>(null)

  // ── follow-ups ──
  const [followUps, setFollowUps] = createSignal<string[]>([])

  // ── cost ──
  const [sessionCost, setSessionCost] = createSignal<SessionCostSummary>({ ...emptyCost })

  // ── error ──
  const [error, setError] = createSignal('')

  // ── UI ──
  const [sidebarOpen, setSidebarOpen] = createSignal(true)

  // ── derived ──
  const currentSession = createMemo(() => sessions().find((s) => s.id === activeSessionId()))
  const hasMessages = createMemo(() => messages().length > 0)

  // ── persist messages when they change ──
  createEffect(
    on(messages, (msgs) => {
      const sid = activeSessionId()
      if (!sid) return
      writeJson(storageMessagesKey(sid), compactForStorage(msgs))
      // update session message count
      setSessions((prev) =>
        prev.map((s) => (s.id === sid ? { ...s, messageCount: msgs.length } : s)),
      )
    }),
  )

  // ── persist session list when it changes ──
  createEffect(
    on(sessions, (list) => {
      writeJson(STORAGE_SESSIONS, list)
    }),
  )

  // ── session management ──

  function createSession(): void {
    const id = generateId()
    const session: ChatSession = {
      id,
      label: `Session ${sessions().length + 1}`,
      createdAt: Date.now(),
      messageCount: 0,
    }
    setSessions((prev) => [session, ...prev])
    setActiveSessionId(id)
    setMessages([])
    setFollowUps([])
    setSessionCost({ ...emptyCost })
    setError('')
  }

  function switchSession(sessionId: string): void {
    if (isStreaming()) return
    setActiveSessionId(sessionId)
    setMessages(readJson<ChatMessage[]>(storageMessagesKey(sessionId), []))
    setFollowUps([])
    setError('')
    recalcSessionCost()
  }

  function deleteSession(sessionId: string): void {
    if (isStreaming()) return
    // fire-and-forget backend logout
    fetch(`${baseUrl()}/agent/logout/${encodeURIComponent(sessionId)}`, { method: 'DELETE' }).catch(() => {})
    localStorage.removeItem(storageMessagesKey(sessionId))
    setSessions((prev) => prev.filter((s) => s.id !== sessionId))
    if (activeSessionId() === sessionId) {
      const remaining = sessions().filter((s) => s.id !== sessionId)
      if (remaining.length) {
        switchSession(remaining[0].id)
      } else {
        createSession()
      }
    }
  }

  function loadSessionsFromStorage(): void {
    const stored = readJson<ChatSession[]>(STORAGE_SESSIONS, [])
    if (stored.length) {
      setSessions(stored)
      switchSession(stored[0].id)
    } else {
      createSession()
    }
  }

  // ── cost helpers ──

  function addCostToSession(cost: CostEvent): void {
    setSessionCost((prev) => ({
      totalCost: prev.totalCost + cost.total_cost,
      totalTokens: prev.totalTokens + cost.usage.total_tokens,
      promptTokens: prev.promptTokens + cost.usage.prompt_tokens,
      completionTokens: prev.completionTokens + cost.usage.completion_tokens,
      reasoningTokens: prev.reasoningTokens + cost.usage.reasoning_tokens,
      requestCount: prev.requestCount + 1,
    }))
  }

  function recalcSessionCost(): void {
    const msgs = messages()
    const summary = { ...emptyCost }
    for (const m of msgs) {
      if (m.cost) {
        summary.totalCost += m.cost.total_cost
        summary.totalTokens += m.cost.usage.total_tokens
        summary.promptTokens += m.cost.usage.prompt_tokens
        summary.completionTokens += m.cost.usage.completion_tokens
        summary.reasoningTokens += m.cost.usage.reasoning_tokens
        summary.requestCount++
      }
    }
    setSessionCost(summary)
  }

  // ── update the last assistant message in-place ──

  function patchLastAssistant(patch: Partial<ChatMessage>): void {
    setMessages((prev) => {
      if (!prev.length) return prev
      const last = prev[prev.length - 1]
      if (last.role !== 'assistant') return prev
      return [...prev.slice(0, -1), { ...last, ...patch }]
    })
  }

  function appendToLastAssistant(field: 'content' | 'reasoning', chunk: string): void {
    setMessages((prev) => {
      if (!prev.length) return prev
      const last = prev[prev.length - 1]
      if (last.role !== 'assistant') return prev
      return [...prev.slice(0, -1), { ...last, [field]: last[field] + chunk }]
    })
  }

  function pushToolCall(tc: ToolCallEvent): void {
    setMessages((prev) => {
      if (!prev.length) return prev
      const last = prev[prev.length - 1]
      if (last.role !== 'assistant') return prev
      return [...prev.slice(0, -1), { ...last, toolCalls: [...last.toolCalls, tc] }]
    })
  }

  // ── send message ──

  async function sendMessage(text: string): Promise<void> {
    const trimmed = text.trim()
    if (!trimmed || isStreaming()) return

    const sid = activeSessionId()
    if (!sid) return

    setError('')
    setFollowUps([])

    // user message
    const userMsg: ChatMessage = {
      id: messageId(),
      role: 'user',
      content: trimmed,
      reasoning: '',
      toolCalls: [],
      cost: null,
      router: null,
      status: 'done',
      timestamp: Date.now(),
    }

    // assistant placeholder
    const assistantMsg: ChatMessage = {
      id: messageId(),
      role: 'assistant',
      content: '',
      reasoning: '',
      toolCalls: [],
      cost: null,
      router: null,
      status: 'streaming',
      timestamp: Date.now(),
    }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInputText('')

    const controller = new AbortController()
    setActiveController(controller)
    setIsStreaming(true)

    try {
      await streamSse(
        `${baseUrl()}/agent/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sid, question: trimmed }),
          signal: controller.signal,
        },
        {
          onOpen: () => {},
          onEvent: (eventName: string, data: string, parsed?: unknown) => {
            switch (eventName) {
              case 'token':
                appendToLastAssistant('content', data)
                break
              case 'reasoning':
                appendToLastAssistant('reasoning', data)
                break
              case 'tool_call': {
                const tc = parsed as ToolCallEvent | undefined
                if (tc && tc.name) pushToolCall(tc)
                break
              }
              case 'cost': {
                const cost = parsed as CostEvent | undefined
                if (cost) {
                  patchLastAssistant({ cost })
                  addCostToSession(cost)
                }
                break
              }
              case 'router': {
                const router = parsed as Record<string, unknown> | undefined
                if (router) patchLastAssistant({ router })
                break
              }
              case 'done':
                patchLastAssistant({ status: 'done' })
                break
              case 'error':
                patchLastAssistant({ status: 'error', content: data || 'Unknown error' })
                setError(data || 'Stream error')
                break
            }
          },
        },
      )

      // ensure done status if stream ended without explicit done event
      patchLastAssistant({ status: 'done' })

      // fetch follow-ups in background
      fetchFollowUps(sid, trimmed)
    } catch (err) {
      const isAbort = err instanceof DOMException && err.name === 'AbortError'
      if (isAbort) {
        patchLastAssistant({ status: 'done' })
      } else {
        const msg = (err as Error).message || 'Request failed'
        patchLastAssistant({ status: 'error' })
        setError(msg)
      }
    } finally {
      setIsStreaming(false)
      setActiveController(null)
    }
  }

  // ── stop generation ──

  function stopGeneration(): void {
    activeController()?.abort()
  }

  // ── retry last message ──

  function retryLastMessage(): void {
    const msgs = messages()
    if (msgs.length < 2) return

    const lastAssistant = msgs[msgs.length - 1]
    const lastUser = msgs[msgs.length - 2]
    if (lastAssistant.role !== 'assistant' || lastUser.role !== 'user') return
    if (lastAssistant.status !== 'error') return

    // remove failed assistant message
    setMessages((prev) => prev.slice(0, -1))
    setError('')

    // re-send the user's question (re-add assistant placeholder inside sendMessage)
    // but we need to also remove the user message since sendMessage will re-add it
    setMessages((prev) => prev.slice(0, -1))
    sendMessage(lastUser.content)
  }

  // ── follow-ups ──

  async function fetchFollowUps(sessionId: string, question: string): Promise<void> {
    try {
      const collected: string[] = []
      let buffer = ''

      await streamSse(
        `${baseUrl()}/agent/follow-up-stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId, question }),
        },
        {
          onOpen: () => {},
          onEvent: (eventName: string, data: string) => {
            if (eventName === 'token') {
              buffer += data
            }
          },
        },
      )

      // try JSON array first
      const parsed = parseMaybeJson(buffer)
      if (Array.isArray(parsed)) {
        collected.push(...parsed.filter((s): s is string => typeof s === 'string'))
      } else if (buffer.trim()) {
        // fallback: split by newlines, filter empties
        collected.push(
          ...buffer
            .split('\n')
            .map((l) => l.replace(/^\d+\.\s*/, '').trim())
            .filter(Boolean),
        )
      }

      setFollowUps(collected.slice(0, 5))
    } catch {
      // non-critical — silently ignore
    }
  }

  // ── init ──
  onMount(() => {
    loadSessionsFromStorage()
  })

  return {
    // session
    sessions,
    activeSessionId,
    currentSession,
    createSession,
    switchSession,
    deleteSession,
    // messages
    messages,
    hasMessages,
    inputText,
    setInputText,
    // streaming
    isStreaming,
    sendMessage,
    stopGeneration,
    retryLastMessage,
    // follow-ups
    followUps,
    // cost
    sessionCost,
    // error
    error,
    setError,
    // UI
    sidebarOpen,
    setSidebarOpen,
  }
}
