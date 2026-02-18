import { For, Show } from 'solid-js'
import { METHOD_STYLE } from '../../config/endpoints'
import type { HistoryItem } from '../../types/api'

export function HistoryPanel(props: { history: HistoryItem[] }) {
  return (
    <section class="card history-panel">
      <div class="panel-head">
        <h3>Execution History</h3>
        <p>Recent 25 endpoint invocations for this page context.</p>
      </div>

      <Show when={props.history.length > 0} fallback={<p class="muted">No history entries yet.</p>}>
        <div class="history-grid">
          <For each={props.history}>
            {(entry) => (
              <div class="history-item">
                <div class="history-top">
                  <span class={`method-chip ${METHOD_STYLE[entry.method]}`}>{entry.method}</span>
                  <strong>{entry.endpointId}</strong>
                </div>
                <div class="history-meta">
                  <span>Status: {entry.status ?? '—'}</span>
                  <span>Duration: {entry.durationMs ? `${entry.durationMs.toFixed(1)}ms` : '—'}</span>
                  <span>{entry.createdAt}</span>
                </div>
                <pre class="code-inline">{entry.url}</pre>
              </div>
            )}
          </For>
        </div>
      </Show>
    </section>
  )
}
