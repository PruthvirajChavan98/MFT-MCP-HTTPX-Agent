import { For, Show, createSignal, onMount } from 'solid-js'
import { fetchSessionCostSummary } from '../../features/admin/service'
import { formatCurrency, formatDateTime, formatNumber } from '../../shared/lib/format'

export default function CostsPage() {
  const [loading, setLoading] = createSignal(true)
  const [error, setError] = createSignal('')
  const [summary, setSummary] = createSignal<{ active_sessions: number; total_cost: number; total_requests: number; sessions: Array<{ session_id: string; total_cost: number; total_requests: number; last_request_at?: string }> } | null>(null)

  onMount(async () => {
    try {
      setSummary(await fetchSessionCostSummary())
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Cost summary failed')
      setError(err.message)
    } finally {
      setLoading(false)
    }
  })

  return (
    <section class="space-y-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Chat Costs</h1>
        <p class="text-sm text-slate-600">Real session-level token cost data from backend Redis tracker.</p>
      </div>

      <Show when={!loading()} fallback={<div class="kpi-card text-sm text-slate-600">Loading costs…</div>}>
        <Show when={!error()} fallback={<div class="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error()}</div>}>
          <div class="grid gap-3 sm:grid-cols-3">
            <div class="kpi-card">
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">Active Sessions</div>
              <div class="mt-2 text-2xl font-semibold text-slate-900">{formatNumber(summary()?.active_sessions ?? 0)}</div>
            </div>
            <div class="kpi-card">
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">Total Requests</div>
              <div class="mt-2 text-2xl font-semibold text-slate-900">{formatNumber(summary()?.total_requests ?? 0)}</div>
            </div>
            <div class="kpi-card">
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">Total Cost</div>
              <div class="mt-2 text-2xl font-semibold text-slate-900">{formatCurrency(summary()?.total_cost ?? 0)}</div>
            </div>
          </div>

          <div class="table-shell">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 text-left text-xs text-slate-500">
                <tr>
                  <th class="px-3 py-2">Session</th>
                  <th class="px-3 py-2">Cost</th>
                  <th class="px-3 py-2">Requests</th>
                  <th class="px-3 py-2">Last Request</th>
                </tr>
              </thead>
              <tbody>
                <For each={summary()?.sessions ?? []}>
                  {(row) => (
                    <tr class="border-t border-slate-100">
                      <td class="px-3 py-2 font-mono text-xs text-slate-700">{row.session_id}</td>
                      <td class="px-3 py-2 text-slate-800">{formatCurrency(row.total_cost)}</td>
                      <td class="px-3 py-2 text-slate-800">{formatNumber(row.total_requests)}</td>
                      <td class="px-3 py-2 text-slate-700">{formatDateTime(row.last_request_at)}</td>
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
