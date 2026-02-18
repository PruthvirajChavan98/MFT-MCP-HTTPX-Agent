import { For } from 'solid-js'
import { METHOD_STYLE } from '../../config/endpoints'
import type { EndpointDef } from '../../types/api'

export function EndpointCatalog(props: {
  title?: string
  search: string
  onSearch: (value: string) => void
  groupedEndpoints: [string, EndpointDef[]][]
  selectedEndpointId: string
  onSelectEndpoint: (endpointId: string) => void
}) {
  return (
    <aside class="card catalog-panel">
      <div class="panel-head">
        <h3>{props.title ?? 'Endpoint Catalog'}</h3>
        <p>Search and run any route.</p>
      </div>

      <input
        class="field"
        placeholder="Search name, path, category..."
        value={props.search}
        onInput={(event) => props.onSearch(event.currentTarget.value)}
      />

      <div class="endpoint-groups">
        <For each={props.groupedEndpoints}>
          {([category, items]) => (
            <section>
              <h4>{category}</h4>
              <div class="endpoint-list">
                <For each={items}>
                  {(endpoint) => (
                    <button
                      class={`endpoint-btn ${props.selectedEndpointId === endpoint.id ? 'active' : ''}`}
                      onClick={() => props.onSelectEndpoint(endpoint.id)}
                    >
                      <span class={`method-chip ${METHOD_STYLE[endpoint.method]}`}>{endpoint.method}</span>
                      <span class="endpoint-title">{endpoint.name}</span>
                      <span class="endpoint-path">{endpoint.path}</span>
                    </button>
                  )}
                </For>
              </div>
            </section>
          )}
        </For>
      </div>
    </aside>
  )
}
