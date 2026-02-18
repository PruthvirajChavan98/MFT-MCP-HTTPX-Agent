import { For, Show, createSignal, onMount } from 'solid-js'
import { useAdminAuth } from '../../features/admin/context'
import { fetchUserAnalytics } from '../../features/admin/service'
import { formatDateTime, formatNumber } from '../../shared/lib/format'

export default function UsersPage() {
  const auth = useAdminAuth()

  const [loading, setLoading] = createSignal(true)
  const [error, setError] = createSignal('')
  const [rows, setRows] = createSignal<Array<{ session_id: string; trace_count: number; success_count: number; error_count: number; avg_latency_ms: number; last_active?: string }>>([])

  onMount(async () => {
    try {
      setRows(await fetchUserAnalytics(auth.adminKey(), 120))
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('User analytics unavailable')
      setError(err.message)
    } finally {
      setLoading(false)
    }
  })

  return (
    <section class="space-y-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Users & Analytics</h1>
        <p class="text-sm text-slate-600">Session-level analytics grouped as user units for production monitoring.</p>
      </div>

      <Show when={!loading()} fallback={<div class="kpi-card text-sm text-slate-600">Loading user analytics…</div>}>
        <Show when={!error()} fallback={<div class="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error()}</div>}>
          <div class="table-shell">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 text-left text-xs text-slate-500">
                <tr>
                  <th class="px-3 py-2">Session/User</th>
                  <th class="px-3 py-2">Traces</th>
                  <th class="px-3 py-2">Success</th>
                  <th class="px-3 py-2">Errors</th>
                  <th class="px-3 py-2">Avg Latency</th>
                  <th class="px-3 py-2">Last Active</th>
                </tr>
              </thead>
              <tbody>
                <For each={rows()}>
                  {(row) => (
                    <tr class="border-t border-slate-100">
                      <td class="px-3 py-2 font-mono text-xs text-slate-700">{row.session_id}</td>
                      <td class="px-3 py-2 text-slate-700">{formatNumber(row.trace_count)}</td>
                      <td class="px-3 py-2 text-slate-700">{formatNumber(row.success_count)}</td>
                      <td class="px-3 py-2 text-slate-700">{formatNumber(row.error_count)}</td>
                      <td class="px-3 py-2 text-slate-700">{Math.round(row.avg_latency_ms)} ms</td>
                      <td class="px-3 py-2 text-xs text-slate-600">{formatDateTime(row.last_active)}</td>
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
