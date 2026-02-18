import { For, Show } from 'solid-js'
import { Bot, RotateCcw, Send, Square, User } from 'lucide-solid'
import type { ChatMessage } from '../../shared/types/chat'

interface ChatPanelProps {
  sessionId: string
  messages: ChatMessage[]
  input: string
  isStreaming: boolean
  error: string
  followUps: string[]
  onInput: (value: string) => void
  onSend: () => void
  onStop: () => void
  onClear: () => void
  onFollowUp: (question: string) => void
}

export default function ChatPanel(props: ChatPanelProps) {
  return (
    <div class="flex h-full min-h-[640px] flex-col overflow-hidden rounded-2xl border border-cyan-100 bg-white shadow-[0_24px_70px_rgba(14,116,144,0.13)]">
      <div class="flex items-center justify-between border-b border-cyan-100 bg-gradient-to-r from-cyan-50 to-sky-50 px-5 py-3">
        <div>
          <div class="text-sm font-semibold text-slate-900">TrustFin Assistant</div>
          <div class="text-xs text-slate-500">Session: {props.sessionId}</div>
        </div>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-slate-300"
          onClick={props.onClear}
          type="button"
        >
          <RotateCcw size={14} />
          New Chat
        </button>
      </div>

      <div class="flex-1 space-y-4 overflow-y-auto bg-slate-50/60 px-4 py-4">
        <Show when={props.messages.length > 0} fallback={<div class="text-sm text-slate-500">Ask anything about loans, repayments, or support workflows.</div>}>
          <For each={props.messages}>
            {(message) => (
              <div class={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div class={`max-w-[86%] rounded-2xl px-4 py-3 shadow-sm ${message.role === 'user' ? 'bg-cyan-600 text-white' : 'border border-slate-200 bg-white text-slate-900'}`}>
                  <div class="mb-2 flex items-center gap-2 text-[11px] opacity-80">
                    <Show when={message.role === 'assistant'} fallback={<User size={12} />}>
                      <Bot size={12} />
                    </Show>
                    <span>{message.role === 'assistant' ? 'Assistant' : 'You'}</span>
                    <span>·</span>
                    <span>{new Date(message.timestamp).toLocaleTimeString()}</span>
                  </div>

                  <p class="whitespace-pre-wrap text-sm leading-relaxed">{message.content || (message.status === 'streaming' ? 'Thinking…' : '')}</p>

                  <Show when={message.reasoning}>
                    <details class="mt-2 rounded-lg bg-cyan-50/70 p-2 text-xs text-slate-700">
                      <summary class="cursor-pointer font-semibold">Reasoning</summary>
                      <p class="mt-1 whitespace-pre-wrap">{message.reasoning}</p>
                    </details>
                  </Show>

                  <Show when={message.toolCalls.length > 0}>
                    <div class="mt-2 space-y-1 text-xs">
                      <For each={message.toolCalls}>
                        {(tool) => (
                          <div class="rounded-md border border-cyan-200 bg-cyan-50 px-2 py-1 text-slate-700">
                            <strong>{tool.name}</strong>
                            <p class="line-clamp-2">{tool.output}</p>
                          </div>
                        )}
                      </For>
                    </div>
                  </Show>

                  <Show when={message.cost}>
                    {(cost) => (
                      <div class="mt-2 text-[11px] text-slate-500">
                        {cost().provider}/{cost().model} · ${cost().total_cost.toFixed(6)} · {cost().usage.total_tokens} tokens
                      </div>
                    )}
                  </Show>
                </div>
              </div>
            )}
          </For>
        </Show>
      </div>

      <Show when={props.followUps.length > 0}>
        <div class="border-t border-cyan-100 bg-white px-4 py-3">
          <div class="mb-2 text-xs font-semibold text-slate-500">Suggested Follow-ups</div>
          <div class="flex flex-wrap gap-2">
            <For each={props.followUps}>
              {(question) => (
                <button
                  class="rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1.5 text-xs text-cyan-900 hover:bg-cyan-100"
                  onClick={() => props.onFollowUp(question)}
                  type="button"
                >
                  {question}
                </button>
              )}
            </For>
          </div>
        </div>
      </Show>

      <div class="border-t border-cyan-100 bg-white px-4 py-3">
        <Show when={props.error}>
          <div class="mb-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{props.error}</div>
        </Show>

        <div class="flex items-end gap-2">
          <textarea
            class="input-base min-h-[46px] flex-1 resize-y"
            rows={2}
            value={props.input}
            onInput={(event) => props.onInput(event.currentTarget.value)}
            placeholder="Ask about products, eligibility, charges, or support"
          />

          <Show
            when={props.isStreaming}
            fallback={
              <button
                class="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-700"
                onClick={props.onSend}
                type="button"
              >
                <Send size={14} />
                Send
              </button>
            }
          >
            <button
              class="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
              onClick={props.onStop}
              type="button"
            >
              <Square size={14} />
              Stop
            </button>
          </Show>
        </div>
      </div>
    </div>
  )
}
