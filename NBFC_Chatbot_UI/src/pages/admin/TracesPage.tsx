import { For, Show, createSignal, onMount } from 'solid-js'
import { fetchEvalTrace, fetchEvalTraces } from '../../features/admin/service'
import { formatDateTime } from '../../shared/lib/format'
import { toPrettyJson } from '../../shared/lib/json'
import type { EvalTraceDetail, EvalTraceSummary } from '../../shared/types/admin'

export default function TracesPage() {
  const [loading, setLoading] = createSignal(true)
  const [error, setError] = createSignal('')
  const [traces, setTraces] = createSignal<EvalTraceSummary[]>([])
  const [selectedId, setSelectedId] = createSignal('')
  const [detail, setDetail] = createSignal<EvalTraceDetail | null>(null)

  async function loadDetail(traceId: string): Promise<void> {
    try {
      setDetail(await fetchEvalTrace(traceId))
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Trace load failed')
      setError(err.message)
    }
  }

  onMount(async () => {
    try {
      const rows = await fetchEvalTraces(120)
      setTraces(rows)
      if (rows.length > 0) {
        setSelectedId(rows[0].trace_id)
        await loadDetail(rows[0].trace_id)
      }
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Traces load failed')
      setError(err.message)
    } finally {
      setLoading(false)
    }
  })

  return (
    <section class="space-y-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Chat Traces</h1>
        <p class="text-sm text-slate-600">Search and inspect full trace events from `/eval` store.</p>
      </div>

      <Show when={!loading()} fallback={<div class="kpi-card text-sm text-slate-600">Loading traces…</div>}>
        <Show when={!error()} fallback={<div class="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error()}</div>}>
          <div class="grid gap-4 lg:grid-cols-[340px_1fr]">
            <div class="table-shell max-h-[700px] overflow-y-auto">
              <For each={traces()}>
                {(trace) => (
                  <button
                    type="button"
                    class={`block w-full border-b border-slate-100 px-3 py-2 text-left hover:bg-slate-50 ${selectedId() === trace.trace_id ? 'bg-cyan-50' : ''}`}
                    onClick={() => {
                      setSelectedId(trace.trace_id)
                      void loadDetail(trace.trace_id)
                    }}
                  >
                    <div class="text-xs font-mono text-slate-600">{trace.trace_id}</div>
                    <div class="mt-1 text-xs text-slate-500">{formatDateTime(trace.started_at)}</div>
                    <div class="mt-1 text-xs text-slate-700">{trace.status} · {trace.model}</div>
                  </button>
                )}
              </For>
            </div>

            <div class="space-y-3">
              <Show when={detail()}>
                {(traceDetail) => (
                  <>
                    <div class="kpi-card">
                      <h2 class="text-sm font-semibold text-slate-900">Trace Summary</h2>
                      <div class="mt-2 grid gap-2 text-xs text-slate-700 sm:grid-cols-2">
                        <div>Trace ID: <span class="font-mono">{traceDetail().trace.trace_id}</span></div>
                        <div>Session: <span class="font-mono">{traceDetail().trace.session_id}</span></div>
                        <div>Status: {traceDetail().trace.status}</div>
                        <div>Latency: {traceDetail().trace.latency_ms ?? 0} ms</div>
                        <div>Provider: {traceDetail().trace.provider ?? 'NA'}</div>
                        <div>Model: {traceDetail().trace.model ?? 'NA'}</div>
                      </div>
                    </div>

                    <div class="table-shell">
                      <div class="border-b border-slate-200 px-4 py-2 text-sm font-semibold text-slate-900">Events ({traceDetail().events.length})</div>
                      <div class="max-h-[350px] overflow-y-auto p-3">
                        <For each={traceDetail().events}>
                          {(event) => (
                            <div class="mb-2 rounded-md border border-slate-200 bg-slate-50 p-2">
                              <div class="text-xs font-semibold text-slate-700">{event.event_type} · {event.name}</div>
                              <Show when={event.text}>
                                <p class="mt-1 text-xs text-slate-700">{event.text}</p>
                              </Show>
                              <Show when={event.payload_json}>
                                <pre class="mt-1 overflow-x-auto rounded bg-white p-2 text-[11px] text-slate-600">{toPrettyJson(event.payload_json)}</pre>
                              </Show>
                            </div>
                          )}
                        </For>
                      </div>
                    </div>
                  </>
                )}
              </Show>
            </div>
          </div>
        </Show>
      </Show>
    </section>
  )
}
