import { For, Show } from 'solid-js'

export function FollowUpChips(props: { suggestions: string[]; onSelect: (text: string) => void }) {
  return (
    <Show when={props.suggestions.length > 0}>
      <div class="chat-followups">
        <For each={props.suggestions}>
          {(suggestion) => (
            <button class="chat-followup-chip" onClick={() => props.onSelect(suggestion)}>
              {suggestion}
            </button>
          )}
        </For>
      </div>
    </Show>
  )
}
