import { createEffect, on, Show } from 'solid-js'

export function ChatInput(props: {
  value: string
  onInput: (text: string) => void
  onSend: () => void
  onStop: () => void
  isStreaming: boolean
  disabled: boolean
}) {
  let textareaRef!: HTMLTextAreaElement

  function handleKeyDown(e: KeyboardEvent): void {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!props.disabled && props.value.trim()) {
        props.onSend()
      }
    }
  }

  // auto-resize textarea
  createEffect(
    on(
      () => props.value,
      () => {
        if (!textareaRef) return
        textareaRef.style.height = 'auto'
        textareaRef.style.height = `${Math.min(textareaRef.scrollHeight, 200)}px`
      },
    ),
  )

  return (
    <div class="chat-input-bar card">
      <textarea
        ref={textareaRef}
        class="field chat-textarea"
        placeholder="Ask a question... (Shift+Enter for newline)"
        value={props.value}
        onInput={(e) => props.onInput(e.currentTarget.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        disabled={props.disabled}
      />
      <Show
        when={props.isStreaming}
        fallback={
          <button
            class="btn primary"
            onClick={props.onSend}
            disabled={props.disabled || !props.value.trim()}
          >
            Send
          </button>
        }
      >
        <button class="btn chat-stop-btn" onClick={props.onStop}>
          Stop
        </button>
      </Show>
    </div>
  )
}
