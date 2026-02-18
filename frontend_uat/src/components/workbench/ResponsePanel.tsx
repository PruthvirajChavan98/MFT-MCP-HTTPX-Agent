import { For, Show } from 'solid-js'
import { formatPretty } from '../../lib/json'
import type { EndpointKind, StreamEvent } from '../../types/api'

export function ResponsePanel(props: {
  endpointKind: EndpointKind
  status: number | null
  durationMs: number | null
  eventsCount: number
  errorMessage: string
  streamAnswerText: string
  streamReasoningText: string
  responseBody: string
  responseHeaders: Record<string, string>
  streamEvents: StreamEvent[]
}) {
  return (
    <section class="card response-panel">
      <div class="response-head">
        <h3>Response & Streaming Telemetry</h3>
        <div class="response-stats">
          <span>
            Status: <strong>{props.status ?? '—'}</strong>
          </span>
          <span>
            Duration: <strong>{props.durationMs ? `${props.durationMs.toFixed(1)}ms` : '—'}</strong>
          </span>
          <span>
            Events: <strong>{props.eventsCount}</strong>
          </span>
        </div>
      </div>

      <Show when={props.errorMessage}>
        <div class="error-box">{props.errorMessage}</div>
      </Show>

      <Show when={props.endpointKind === 'sse'}>
        <div class="stream-layout">
          <article>
            <h4>Answer Stream</h4>
            <pre class="code-block stream-text">{props.streamAnswerText || 'No answer tokens yet.'}</pre>
          </article>
          <article>
            <h4>Reasoning Stream</h4>
            <pre class="code-block stream-text">{props.streamReasoningText || 'No reasoning tokens yet.'}</pre>
          </article>
        </div>
      </Show>

      <article>
        <h4>Response Body</h4>
        <pre class="code-block">{props.responseBody || 'No response yet.'}</pre>
      </article>

      <article>
        <h4>Response Headers</h4>
        <pre class="code-block">{formatPretty(props.responseHeaders)}</pre>
      </article>

      <Show when={props.streamEvents.length > 0}>
        <article>
          <h4>SSE Event Feed</h4>
          <div class="stream-feed">
            <For each={props.streamEvents}>
              {(entry) => (
                <div class="stream-row">
                  <div class="stream-meta">
                    <span>{entry.event}</span>
                    <span>{entry.timestamp}</span>
                  </div>
                  <pre class="code-inline">{entry.parsed ? formatPretty(entry.parsed) : entry.data}</pre>
                </div>
              )}
            </For>
          </div>
        </article>
      </Show>
    </section>
  )
}
