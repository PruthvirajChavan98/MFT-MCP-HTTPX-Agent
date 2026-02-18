import { For, Show, createSignal, onMount } from 'solid-js'
import { useAdminAuth } from '../../features/admin/context'
import { fetchGuardrailEvents } from '../../features/admin/service'
import { formatDateTime } from '../../shared/lib/format'

export default function GuardrailsPage() {
  const auth = useAdminAuth()

  const [loading, setLoading] = createSignal(true)
  const [error, setError] = createSignal('')
  const [rows, setRows] = createSignal<Array<{ event_time: string; session_id: string; risk_score: number; risk_decision: string; request_path?: string; reasons: string[] }>>([])

  onMount(async () => {
    try {
      setRows(await fetchGuardrailEvents(auth.adminKey(), 120))
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Guardrail events unavailable')
      setError(err.message)
    } finally {
      setLoading(false)
    }
  })

  return (
    <section class="space-y-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Guardrails</h1>
        <p class="text-sm text-slate-600">Security risk events from PostgreSQL session-security telemetry.</p>
      </div>

      <Show when={!loading()} fallback={<div class="kpi-card text-sm text-slate-600">Loading guardrail events…</div>}>
        <Show when={!error()} fallback={<div class="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error()}</div>}>
          <div class="table-shell">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 text-left text-xs text-slate-500">
                <tr>
                  <th class="px-3 py-2">Time</th>
                  <th class="px-3 py-2">Session</th>
                  <th class="px-3 py-2">Score</th>
                  <th class="px-3 py-2">Decision</th>
                  <th class="px-3 py-2">Path</th>
                  <th class="px-3 py-2">Reasons</th>
                </tr>
              </thead>
              <tbody>
                <For each={rows()}>
                  {(row) => (
                    <tr class="border-t border-slate-100 align-top">
                      <td class="px-3 py-2 text-xs text-slate-600">{formatDateTime(row.event_time)}</td>
                      <td class="px-3 py-2 font-mono text-xs text-slate-700">{row.session_id}</td>
                      <td class="px-3 py-2 text-slate-700">{row.risk_score.toFixed(3)}</td>
                      <td class="px-3 py-2 text-slate-700">{row.risk_decision}</td>
                      <td class="px-3 py-2 text-xs text-slate-600">{row.request_path ?? 'NA'}</td>
                      <td class="px-3 py-2 text-xs text-slate-600">{row.reasons.join(', ') || 'none'}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>
        </Show>
      </Show>
    </section>
  )
}
