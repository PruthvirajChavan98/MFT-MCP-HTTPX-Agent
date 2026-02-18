import { createSignal, Show } from 'solid-js'
import type { ToolCallEvent } from '../../types/chat'

export function ToolCallCard(props: { toolCall: ToolCallEvent }) {
  const [expanded, setExpanded] = createSignal(false)

  return (
    <div class="chat-tool-call card">
      <button class="chat-tool-header" onClick={() => setExpanded(!expanded())}>
        <span class="method-chip method-post">Tool</span>
        <strong>{props.toolCall.name}</strong>
        <span class="chat-tool-expand">{expanded() ? '\u25BE' : '\u25B8'}</span>
      </button>
      <Show when={expanded()}>
        <pre class="code-block">{props.toolCall.output}</pre>
      </Show>
    </div>
  )
}
