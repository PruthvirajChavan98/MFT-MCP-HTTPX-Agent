import { Show } from 'solid-js'
import { asBodyPreview } from '../../lib/curl'
import { useApiWorkbench } from '../../hooks/useApiWorkbench'
import type { EndpointDef } from '../../types/api'
import { EndpointCatalog } from './EndpointCatalog'
import { HistoryPanel } from './HistoryPanel'
import { RequestBuilder } from './RequestBuilder'
import { ResponsePanel } from './ResponsePanel'
import { PageHeader } from '../layout/PageHeader'

export function ApiWorkbench(props: {
  title: string
  subtitle: string
  endpoints: EndpointDef[]
  rightLabel?: string
  rightValue?: string
}) {
  const state = useApiWorkbench({ endpoints: props.endpoints })

  const selectedEndpoint = () => state.selectedEndpoint()

  return (
    <div class="page-stack">
      <PageHeader
        title={props.title}
        subtitle={props.subtitle}
        rightLabel={props.rightLabel ?? 'Endpoints'}
        rightValue={props.rightValue ?? String(props.endpoints.length)}
      />

      <Show when={selectedEndpoint()} fallback={<section class="card"><p>No endpoints configured for this view.</p></section>}>
        {(endpoint) => (
          <div class="workbench-grid">
            <EndpointCatalog
              search={state.search()}
              onSearch={state.setSearch}
              groupedEndpoints={state.groupedEndpoints()}
              selectedEndpointId={state.selectedEndpointId()}
              onSelectEndpoint={state.setSelectedEndpointId}
            />

            <div class="workbench-main">
              <RequestBuilder
                endpoint={endpoint()}
                baseUrl={state.baseUrl()}
                requestUrl={state.requestUrl()}
                pathParamsText={state.pathParamsText()}
                queryText={state.queryText()}
                headersText={state.headersText()}
                bodyText={state.bodyText()}
                loading={state.loading()}
                onBaseUrl={state.setBaseUrl}
                onPathParams={state.setPathParamsText}
                onQuery={state.setQueryText}
                onHeaders={state.setHeadersText}
                onBody={state.setBodyText}
                onFile={state.setUploadFile}
                onRun={state.executeRequest}
                onCancel={state.cancelRequest}
                curlPreview={state.curlPreview()}
              />

              <ResponsePanel
                endpointKind={endpoint().kind}
                status={state.responseStatus()}
                durationMs={state.responseDurationMs()}
                eventsCount={state.streamEvents().length}
                errorMessage={state.errorMessage()}
                streamAnswerText={state.streamAnswerText()}
                streamReasoningText={state.streamReasoningText()}
                responseBody={state.responseBody()}
                responseHeaders={state.responseHeaders()}
                streamEvents={state.streamEvents()}
              />

              <HistoryPanel history={state.history()} />
            </div>
          </div>
        )}
      </Show>

      <footer class="page-footer">
        <p>
          Body mode: <strong>{selectedEndpoint()?.bodyMode ?? '—'}</strong> · Stream mode:{' '}
          <strong>{selectedEndpoint()?.kind ?? '—'}</strong> · Payload preview:{' '}
          <strong>{asBodyPreview(selectedEndpoint()?.bodyMode ?? 'none', state.bodyText(), !!state.uploadFile())}</strong>
        </p>
      </footer>
    </div>
  )
}
