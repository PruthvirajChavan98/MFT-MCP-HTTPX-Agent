import { For, Show, createSignal, onMount } from 'solid-js'
import { fetchQuestionTypes } from '../../features/admin/service'
import { formatNumber, formatPct } from '../../shared/lib/format'

export default function CategoriesPage() {
  const [loading, setLoading] = createSignal(true)
  const [error, setError] = createSignal('')
  const [rows, setRows] = createSignal<Array<{ reason: string; count: number; pct: number }>>([])

  onMount(async () => {
    try {
      setRows(await fetchQuestionTypes(100))
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Category load failed')
      setError(err.message)
    } finally {
      setLoading(false)
    }
  })

  return (
    <section class="space-y-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Question Categories</h1>
        <p class="text-sm text-slate-600">Derived from router reasons in evaluation traces.</p>
      </div>

      <Show when={!loading()} fallback={<div class="kpi-card text-sm text-slate-600">Loading categories…</div>}>
        <Show when={!error()} fallback={<div class="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error()}</div>}>
          <div class="table-shell">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 text-left text-xs text-slate-500">
                <tr>
                  <th class="px-3 py-2">Category</th>
                  <th class="px-3 py-2">Count</th>
                  <th class="px-3 py-2">Share</th>
                </tr>
              </thead>
              <tbody>
                <For each={rows()}>
                  {(row) => (
                    <tr class="border-t border-slate-100">
                      <td class="px-3 py-2 text-slate-800">{row.reason}</td>
                      <td class="px-3 py-2 text-slate-700">{formatNumber(row.count)}</td>
                      <td class="px-3 py-2 text-slate-700">{formatPct(row.pct)}</td>
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
