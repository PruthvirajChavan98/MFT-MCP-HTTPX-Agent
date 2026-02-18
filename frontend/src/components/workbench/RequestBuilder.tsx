import { Show } from 'solid-js'
import { METHOD_STYLE } from '../../config/endpoints'
import type { EndpointDef } from '../../types/api'

export function RequestBuilder(props: {
  endpoint: EndpointDef
  baseUrl: string
  requestUrl: string
  pathParamsText: string
  queryText: string
  headersText: string
  bodyText: string
  loading: boolean
  onBaseUrl: (value: string) => void
  onPathParams: (value: string) => void
  onQuery: (value: string) => void
  onHeaders: (value: string) => void
  onBody: (value: string) => void
  onFile: (file: File | null) => void
  onRun: () => void
  onCancel: () => void
  curlPreview: string
}) {
  return (
    <section class="card request-panel">
      <div class="request-head">
        <div>
          <h3>{props.endpoint.name}</h3>
          <p>{props.endpoint.description}</p>
        </div>
        <span class={`method-chip big ${METHOD_STYLE[props.endpoint.method]}`}>{props.endpoint.method}</span>
      </div>

      <div class="field-grid">
        <label>
          <span>Base URL</span>
          <input class="field" value={props.baseUrl} onInput={(event) => props.onBaseUrl(event.currentTarget.value)} />
        </label>
        <label>
          <span>Resolved Endpoint</span>
          <input class="field mono" value={props.requestUrl || props.endpoint.path} readOnly />
        </label>
      </div>

      <div class="field-grid two-col">
        <label>
          <span>Path Params (JSON)</span>
          <textarea class="field area mono" value={props.pathParamsText} onInput={(event) => props.onPathParams(event.currentTarget.value)} />
        </label>
        <label>
          <span>Query Params (JSON)</span>
          <textarea class="field area mono" value={props.queryText} onInput={(event) => props.onQuery(event.currentTarget.value)} />
        </label>
      </div>

      <label>
        <span>Headers (JSON)</span>
        <textarea class="field area mono" value={props.headersText} onInput={(event) => props.onHeaders(event.currentTarget.value)} />
      </label>

      <Show when={props.endpoint.bodyMode === 'json'}>
        <label>
          <span>Body (JSON)</span>
          <textarea class="field area tall mono" value={props.bodyText} onInput={(event) => props.onBody(event.currentTarget.value)} />
        </label>
      </Show>

      <Show when={props.endpoint.bodyMode === 'multipart'}>
        <label>
          <span>Upload File</span>
          <input class="field" type="file" onChange={(event) => props.onFile(event.currentTarget.files?.[0] ?? null)} />
        </label>
      </Show>

      <div class="actions">
        <button class="btn primary" disabled={props.loading} onClick={props.onRun}>
          {props.loading ? 'Running...' : 'Run Endpoint'}
        </button>
        <button class="btn" disabled={!props.loading} onClick={props.onCancel}>
          Cancel
        </button>
      </div>

      <label>
        <span>cURL Preview</span>
        <pre class="code-block">{props.curlPreview}</pre>
      </label>
    </section>
  )
}
