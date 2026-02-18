import { For, Show } from 'solid-js'
import type { ChatSession, SessionCostSummary } from '../../types/chat'

export function SessionSidebar(props: {
  sessions: ChatSession[]
  activeSessionId: string
  sessionCost: SessionCostSummary
  onSelect: (id: string) => void
  onCreate: () => void
  onDelete: (id: string) => void
  isOpen: boolean
  onToggle: () => void
}) {
  return (
    <aside class={`chat-sidebar ${props.isOpen ? 'chat-sidebar-open' : ''}`}>
      <div class="chat-sidebar-header">
        <h3>Sessions</h3>
        <button class="btn primary" onClick={props.onCreate}>+ New</button>
      </div>

      <div class="chat-session-list">
        <For each={props.sessions}>
          {(session) => (
            <div
              class={`chat-session-item ${session.id === props.activeSessionId ? 'active' : ''}`}
              onClick={() => props.onSelect(session.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter') props.onSelect(session.id) }}
            >
              <span class="chat-session-label">{session.label}</span>
              <small class="muted">{session.messageCount} messages</small>
              <button
                class="chat-session-delete"
                onClick={(e) => {
                  e.stopPropagation()
                  props.onDelete(session.id)
                }}
                title="Delete session"
              >
                x
              </button>
            </div>
          )}
        </For>
      </div>

      <Show when={props.sessionCost.requestCount > 0}>
        <div class="chat-cost-summary">
          <div>
            <span class="muted">Total Cost</span>
            <strong>${props.sessionCost.totalCost.toFixed(4)}</strong>
          </div>
          <div>
            <span class="muted">Tokens</span>
            <strong>{props.sessionCost.totalTokens.toLocaleString()}</strong>
          </div>
          <div>
            <span class="muted">Requests</span>
            <strong>{props.sessionCost.requestCount}</strong>
          </div>
        </div>
      </Show>
    </aside>
  )
}
