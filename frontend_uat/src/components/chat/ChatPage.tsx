import { createEffect, For, on, Show } from 'solid-js'
import { useChat } from '../../hooks/useChat'
import { SessionSidebar } from './SessionSidebar'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { FollowUpChips } from './FollowUpChips'

export function ChatPage() {
  const chat = useChat()
  let messagesEndRef!: HTMLDivElement
  let messagesContainerRef!: HTMLDivElement

  function isNearBottom(): boolean {
    if (!messagesContainerRef) return true
    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef
    return scrollTop + clientHeight >= scrollHeight - 120
  }

  // auto-scroll during streaming when user is near bottom
  createEffect(
    on(chat.messages, () => {
      if (isNearBottom()) {
        requestAnimationFrame(() => {
          messagesEndRef?.scrollIntoView({ behavior: 'smooth' })
        })
      }
    }),
  )

  function handleSend(): void {
    const text = chat.inputText().trim()
    if (!text) return
    chat.sendMessage(text)
  }

  function handleFollowUp(text: string): void {
    chat.sendMessage(text)
  }

  return (
    <div class="page-stack">
      <div class="card page-header">
        <div>
          <p class="eyebrow">Chat</p>
          <h2>Agent Chat</h2>
        </div>
        <div class="header-metric">
          <span>Session</span>
          <strong>{chat.activeSessionId() ? chat.activeSessionId().slice(0, 20) : 'None'}</strong>
        </div>
      </div>

      <div class="chat-layout">
        <SessionSidebar
          sessions={chat.sessions()}
          activeSessionId={chat.activeSessionId()}
          sessionCost={chat.sessionCost()}
          onSelect={(id) => chat.switchSession(id)}
          onCreate={() => chat.createSession()}
          onDelete={(id) => chat.deleteSession(id)}
          isOpen={chat.sidebarOpen()}
          onToggle={() => chat.setSidebarOpen(!chat.sidebarOpen())}
        />

        <div class="chat-main">
          <button
            class="btn chat-sidebar-toggle"
            onClick={() => chat.setSidebarOpen(!chat.sidebarOpen())}
          >
            Sessions
          </button>

          <Show when={chat.error()}>
            <div class="error-box">
              {chat.error()}
              <button class="btn" onClick={() => chat.retryLastMessage()} style={{ "margin-left": '0.5rem' }}>
                Retry
              </button>
              <button class="btn" onClick={() => chat.setError('')} style={{ "margin-left": '0.35rem' }}>
                Dismiss
              </button>
            </div>
          </Show>

          <div class="chat-messages" ref={messagesContainerRef}>
            <Show
              when={chat.hasMessages()}
              fallback={
                <div class="chat-empty">
                  <h3>Start a conversation</h3>
                  <p class="muted">Ask the agent anything. Responses stream in real-time with reasoning, tool calls, and cost tracking.</p>
                </div>
              }
            >
              <For each={chat.messages()}>
                {(msg) => <MessageBubble message={msg} />}
              </For>
            </Show>
            <div ref={messagesEndRef} />
          </div>

          <FollowUpChips
            suggestions={chat.followUps()}
            onSelect={handleFollowUp}
          />

          <ChatInput
            value={chat.inputText()}
            onInput={(text) => chat.setInputText(text)}
            onSend={handleSend}
            onStop={() => chat.stopGeneration()}
            isStreaming={chat.isStreaming()}
            disabled={!chat.activeSessionId()}
          />
        </div>
      </div>
    </div>
  )
}
