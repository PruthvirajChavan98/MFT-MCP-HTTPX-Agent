import { For, Show } from 'solid-js'
import type { ChatMessage } from '../../types/chat'
import { renderMarkdown } from '../../lib/markdown'
import { ReasoningBlock } from './ReasoningBlock'
import { ToolCallCard } from './ToolCallCard'
import { CostBadge } from './CostBadge'

function formatTime(ts: number): string {
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

export function MessageBubble(props: { message: ChatMessage }) {
  const isUser = () => props.message.role === 'user'
  const isStreaming = () => props.message.status === 'streaming'
  const isError = () => props.message.status === 'error'

  return (
    <div class={`chat-bubble ${isUser() ? 'chat-bubble-user' : 'chat-bubble-assistant'} ${isError() ? 'chat-bubble-error' : ''}`}>
      <Show when={!isUser() && props.message.reasoning}>
        <ReasoningBlock text={props.message.reasoning} />
      </Show>

      <Show when={!isUser() && props.message.toolCalls.length > 0}>
        <For each={props.message.toolCalls}>
          {(tc) => <ToolCallCard toolCall={tc} />}
        </For>
      </Show>

      <Show
        when={!isUser()}
        fallback={<div class="chat-content">{props.message.content}</div>}
      >
        <div class="chat-content" innerHTML={renderMarkdown(props.message.content)} />
        <Show when={isStreaming()}>
          <span class="chat-cursor" />
        </Show>
      </Show>

      <div class="chat-bubble-footer">
        <span class="chat-timestamp">{formatTime(props.message.timestamp)}</span>
        <Show when={props.message.cost}>
          <CostBadge cost={props.message.cost!} />
        </Show>
      </div>
    </div>
  )
}
