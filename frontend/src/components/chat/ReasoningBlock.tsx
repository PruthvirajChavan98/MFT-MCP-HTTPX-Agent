import { createSignal, Show } from 'solid-js'

export function ReasoningBlock(props: { text: string }) {
  const [expanded, setExpanded] = createSignal(false)

  return (
    <div class="chat-reasoning">
      <button class="chat-reasoning-toggle" onClick={() => setExpanded(!expanded())}>
        <span>{expanded() ? '\u25BE' : '\u25B8'} Thinking</span>
        <small class="muted">{props.text.length} chars</small>
      </button>
      <Show when={expanded()}>
        <pre class="chat-reasoning-content mono">{props.text}</pre>
      </Show>
    </div>
  )
}
