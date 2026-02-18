import { For, Show, createSignal, onMount } from 'solid-js'
import { useAdminAuth } from '../../features/admin/context'
import { extractTraceQuestion, fetchConversations } from '../../features/admin/service'
import { formatDateTime } from '../../shared/lib/format'
import type { EvalTraceSummary } from '../../shared/types/admin'

export default function ConversationsPage() {
  const auth = useAdminAuth()

  const [loading, setLoading] = createSignal(true)
  const [error, setError] = createSignal('')
  const [rows, setRows] = createSignal<EvalTraceSummary[]>([])

  onMount(async () => {
    try {
      setRows(await fetchConversations(auth.adminKey(), 120))
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Conversation load failed')
      setError(err.message)
    } finally {
      setLoading(false)
    }
  })

  return (
    <section class="space-y-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Conversations</h1>
        <p class="text-sm text-slate-600">Recent Q&A extracted from committed trace records.</p>
      </div>

      <Show when={!loading()} fallback={<div class="kpi-card text-sm text-slate-600">Loading conversations…</div>}>
        <Show when={!error()} fallback={<div class="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error()}</div>}>
          <div class="table-shell">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 text-left text-xs text-slate-500">
                <tr>
                  <th class="px-3 py-2">Time</th>
                  <th class="px-3 py-2">Question</th>
                  <th class="px-3 py-2">Response</th>
                  <th class="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                <For each={rows()}>
                  {(row) => (
                    <tr class="border-t border-slate-100 align-top">
                      <td class="px-3 py-2 text-xs text-slate-600">{formatDateTime(row.started_at)}</td>
                      <td class="px-3 py-2 text-slate-800">{extractTraceQuestion(row) || 'NA'}</td>
                      <td class="px-3 py-2 text-slate-700">{row.final_output || 'NA'}</td>
                      <td class="px-3 py-2 text-slate-700">{row.status || 'NA'}</td>
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
