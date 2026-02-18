import { For, Show, createMemo, createSignal, onMount } from 'solid-js'
import {
  fetchEvalTraces,
  fetchMetricsSummary,
  fetchQuestionTypes,
  fetchSessionCostSummary,
} from '../../features/admin/service'
import { formatCurrency, formatDateTime, formatNumber, formatPct } from '../../shared/lib/format'

interface DashboardData {
  traces: number
  successRate: number
  avgLatencyMs: number
  totalCost: number
  totalRequests: number
  categories: Array<{ reason: string; count: number; pct: number }>
  updatedAt: string
}

export default function DashboardPage() {
  const [loading, setLoading] = createSignal(true)
  const [error, setError] = createSignal('')
  const [data, setData] = createSignal<DashboardData | null>(null)

  const cards = createMemo(() => {
    const d = data()
    if (!d) return []
    return [
      { label: 'Traces', value: formatNumber(d.traces) },
      { label: 'Success Rate', value: formatPct(d.successRate) },
      { label: 'Avg Latency', value: `${Math.round(d.avgLatencyMs)} ms` },
      { label: 'Total Cost', value: formatCurrency(d.totalCost) },
      { label: 'Total Requests', value: formatNumber(d.totalRequests) },
    ]
  })

  onMount(async () => {
    try {
      setLoading(true)
      setError('')

      const [traces, summary, categories] = await Promise.all([
        fetchEvalTraces(200),
        fetchSessionCostSummary(),
        fetchQuestionTypes(50),
        fetchMetricsSummary(),
      ])

      const successCount = traces.filter((item) => item.status === 'success').length
      const successRate = traces.length ? successCount / traces.length : 0
      const avgLatencyMs =
        traces.length > 0 ? traces.reduce((sum, item) => sum + (item.latency_ms ?? 0), 0) / traces.length : 0

      setData({
        traces: traces.length,
        successRate,
        avgLatencyMs,
        totalCost: summary.total_cost ?? 0,
        totalRequests: summary.total_requests ?? 0,
        categories,
        updatedAt: new Date().toISOString(),
      })
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Dashboard load failed')
      setError(err.message)
    } finally {
      setLoading(false)
    }
  })

  return (
    <section class="space-y-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p class="text-sm text-slate-600">Live operational summary generated from backend traces and session-cost telemetry.</p>
      </div>

      <Show when={!loading()} fallback={<div class="kpi-card text-sm text-slate-600">Loading dashboard…</div>}>
        <Show when={!error()} fallback={<div class="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error()}</div>}>
          <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <For each={cards()}>
              {(card) => (
                <div class="kpi-card">
                  <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">{card.label}</p>
                  <p class="mt-2 text-xl font-semibold text-slate-900">{card.value}</p>
                </div>
              )}
            </For>
          </div>

          <div class="table-shell">
            <div class="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-900">Question Categories</div>
            <table class="w-full text-sm">
              <thead class="bg-slate-50 text-left text-xs text-slate-500">
                <tr>
                  <th class="px-4 py-2">Category</th>
                  <th class="px-4 py-2">Count</th>
                  <th class="px-4 py-2">Share</th>
                </tr>
              </thead>
              <tbody>
                <For each={data()?.categories ?? []}>
                  {(row) => (
                    <tr class="border-t border-slate-100">
                      <td class="px-4 py-2 text-slate-800">{row.reason}</td>
                      <td class="px-4 py-2 text-slate-700">{formatNumber(row.count)}</td>
                      <td class="px-4 py-2 text-slate-700">{formatPct(row.pct)}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>

          <div class="text-xs text-slate-500">Updated: {formatDateTime(data()?.updatedAt)}</div>
        </Show>
      </Show>
    </section>
  )
}
