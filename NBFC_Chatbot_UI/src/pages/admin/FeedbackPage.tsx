import { For, Show, createSignal, onMount } from 'solid-js'
import { useAdminAuth } from '../../features/admin/context'
import { createFeedback, feedbackSummary, listFeedback } from '../../features/admin/service'
import { formatDateTime } from '../../shared/lib/format'

export default function FeedbackPage() {
  const auth = useAdminAuth()

  const [loading, setLoading] = createSignal(true)
  const [error, setError] = createSignal('')
  const [status, setStatus] = createSignal('')
  const [records, setRecords] = createSignal<Array<{ id: string; session_id: string; trace_id?: string | null; rating: 'thumbs_up' | 'thumbs_down'; comment?: string | null; category?: string | null; created_at: string }>>([])
  const [summary, setSummary] = createSignal<{ total: number; thumbs_up: number; thumbs_down: number; positive_rate: number } | null>(null)

  const [sessionId, setSessionId] = createSignal(localStorage.getItem('nbfc_chat_session_id') ?? 'session_demo')
  const [traceId, setTraceId] = createSignal('')
  const [rating, setRating] = createSignal<'thumbs_up' | 'thumbs_down'>('thumbs_up')
  const [category, setCategory] = createSignal('general')
  const [comment, setComment] = createSignal('')

  async function load(): Promise<void> {
    try {
      setLoading(true)
      setError('')
      const [rows, stats] = await Promise.all([
        listFeedback(auth.adminKey(), 150),
        feedbackSummary(auth.adminKey()),
      ])
      setRecords(rows)
      setSummary(stats)
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Feedback load failed')
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function submitFeedback(): Promise<void> {
    try {
      await createFeedback({
        session_id: sessionId(),
        trace_id: traceId().trim() || undefined,
        rating: rating(),
        comment: comment().trim() || undefined,
        category: category().trim() || undefined,
      })
      setStatus('Feedback submitted')
      setTraceId('')
      setComment('')
      await load()
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Feedback submit failed')
      setError(err.message)
    }
  }

  onMount(() => {
    void load()
  })

  return (
    <section class="space-y-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Feedback</h1>
        <p class="text-sm text-slate-600">Persisted thumbs-up/down feedback with comment and category dimensions.</p>
      </div>

      <div class="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 lg:grid-cols-2">
        <label class="text-xs text-slate-600">
          <span class="mb-1 block font-semibold">Session ID</span>
          <input value={sessionId()} onInput={(e) => setSessionId(e.currentTarget.value)} class="input-base w-full" />
        </label>

        <label class="text-xs text-slate-600">
          <span class="mb-1 block font-semibold">Trace ID (optional)</span>
          <input value={traceId()} onInput={(e) => setTraceId(e.currentTarget.value)} class="input-base w-full" />
        </label>

        <label class="text-xs text-slate-600">
          <span class="mb-1 block font-semibold">Rating</span>
          <select value={rating()} onChange={(e) => setRating(e.currentTarget.value as 'thumbs_up' | 'thumbs_down')} class="input-base w-full">
            <option value="thumbs_up">thumbs_up</option>
            <option value="thumbs_down">thumbs_down</option>
          </select>
        </label>

        <label class="text-xs text-slate-600">
          <span class="mb-1 block font-semibold">Category</span>
          <input value={category()} onInput={(e) => setCategory(e.currentTarget.value)} class="input-base w-full" />
        </label>

        <label class="text-xs text-slate-600 lg:col-span-2">
          <span class="mb-1 block font-semibold">Comment</span>
          <textarea value={comment()} onInput={(e) => setComment(e.currentTarget.value)} class="input-base min-h-[100px] w-full" />
        </label>

        <div class="lg:col-span-2">
          <button class="rounded-lg bg-cyan-600 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-700" type="button" onClick={() => void submitFeedback()}>
            Submit Feedback
          </button>
        </div>
      </div>

      <Show when={summary()}>
        {(stats) => (
          <div class="grid gap-3 sm:grid-cols-4">
            <div class="kpi-card"><p class="text-xs text-slate-500">Total</p><p class="text-lg font-semibold">{stats().total}</p></div>
            <div class="kpi-card"><p class="text-xs text-slate-500">Thumbs Up</p><p class="text-lg font-semibold">{stats().thumbs_up}</p></div>
            <div class="kpi-card"><p class="text-xs text-slate-500">Thumbs Down</p><p class="text-lg font-semibold">{stats().thumbs_down}</p></div>
            <div class="kpi-card"><p class="text-xs text-slate-500">Positive Rate</p><p class="text-lg font-semibold">{(stats().positive_rate * 100).toFixed(1)}%</p></div>
          </div>
        )}
      </Show>

      <Show when={status()}>
        <div class="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{status()}</div>
      </Show>
      <Show when={error()}>
        <div class="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error()}</div>
      </Show>

      <Show when={!loading()} fallback={<div class="kpi-card text-sm text-slate-600">Loading feedback…</div>}>
        <div class="table-shell">
          <table class="w-full text-sm">
            <thead class="bg-slate-50 text-left text-xs text-slate-500">
              <tr>
                <th class="px-3 py-2">Time</th>
                <th class="px-3 py-2">Session</th>
                <th class="px-3 py-2">Trace</th>
                <th class="px-3 py-2">Rating</th>
                <th class="px-3 py-2">Category</th>
                <th class="px-3 py-2">Comment</th>
              </tr>
            </thead>
            <tbody>
              <For each={records()}>
                {(row) => (
                  <tr class="border-t border-slate-100 align-top">
                    <td class="px-3 py-2 text-xs text-slate-600">{formatDateTime(row.created_at)}</td>
                    <td class="px-3 py-2 font-mono text-xs text-slate-700">{row.session_id}</td>
                    <td class="px-3 py-2 font-mono text-xs text-slate-700">{row.trace_id ?? 'NA'}</td>
                    <td class="px-3 py-2 text-slate-700">{row.rating}</td>
                    <td class="px-3 py-2 text-slate-700">{row.category ?? 'NA'}</td>
                    <td class="px-3 py-2 text-slate-700">{row.comment ?? 'NA'}</td>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
        </div>
      </Show>
    </section>
  )
}
