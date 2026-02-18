import { For, Show, createSignal, onMount } from 'solid-js'
import { useAdminAuth } from '../../features/admin/context'
import { deleteFaq, fetchFaqs, ingestFaqBatch, updateFaq } from '../../features/admin/service'

export default function KnowledgeBasePage() {
  const auth = useAdminAuth()

  const [loading, setLoading] = createSignal(true)
  const [error, setError] = createSignal('')
  const [status, setStatus] = createSignal('')
  const [records, setRecords] = createSignal<Array<{ question: string; answer: string }>>([])

  const [newQuestion, setNewQuestion] = createSignal('')
  const [newAnswer, setNewAnswer] = createSignal('')

  async function loadFaqs(): Promise<void> {
    try {
      setLoading(true)
      setError('')
      const data = await fetchFaqs(auth.adminKey(), 300, 0)
      setRecords(data.map((item) => ({ question: item.question, answer: item.answer })))
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Failed to load knowledge base')
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function addRecord(): Promise<void> {
    const question = newQuestion().trim()
    const answer = newAnswer().trim()
    if (!question || !answer) return

    try {
      setStatus('Uploading item…')
      await ingestFaqBatch(auth.adminKey(), [{ question, answer }], auth.openrouterKey(), auth.groqKey())
      setStatus('FAQ item ingested successfully')
      setNewQuestion('')
      setNewAnswer('')
      await loadFaqs()
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('FAQ ingest failed')
      setError(err.message)
    }
  }

  async function saveEdit(originalQuestion: string, nextQuestion: string, nextAnswer: string): Promise<void> {
    try {
      await updateFaq(auth.adminKey(), {
        original_question: originalQuestion,
        new_question: nextQuestion,
        new_answer: nextAnswer,
      })
      setStatus('FAQ updated')
      await loadFaqs()
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('FAQ update failed')
      setError(err.message)
    }
  }

  async function removeRecord(question: string): Promise<void> {
    try {
      await deleteFaq(auth.adminKey(), question)
      setStatus('FAQ deleted')
      await loadFaqs()
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('FAQ delete failed')
      setError(err.message)
    }
  }

  onMount(() => {
    void loadFaqs()
  })

  return (
    <section class="space-y-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Knowledge Base</h1>
        <p class="text-sm text-slate-600">Manage FAQ entries using live backend admin endpoints.</p>
      </div>

      <div class="grid gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <h2 class="text-sm font-semibold text-slate-900">Add FAQ Item</h2>
        <input value={newQuestion()} onInput={(e) => setNewQuestion(e.currentTarget.value)} class="input-base" placeholder="Question" />
        <textarea value={newAnswer()} onInput={(e) => setNewAnswer(e.currentTarget.value)} class="input-base min-h-[100px]" placeholder="Answer" />
        <div>
          <button onClick={() => void addRecord()} class="rounded-lg bg-cyan-600 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-700" type="button">
            Ingest
          </button>
        </div>
      </div>

      <Show when={status()}>
        <div class="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{status()}</div>
      </Show>

      <Show when={!error()} fallback={<div class="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error()}</div>}>
        <Show when={!loading()} fallback={<div class="kpi-card text-sm text-slate-600">Loading knowledge base…</div>}>
          <div class="table-shell">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 text-left text-xs text-slate-500">
                <tr>
                  <th class="px-3 py-2">Question</th>
                  <th class="px-3 py-2">Answer</th>
                  <th class="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                <For each={records()}>
                  {(record) => {
                    const [editQ, setEditQ] = createSignal(record.question)
                    const [editA, setEditA] = createSignal(record.answer)
                    return (
                      <tr class="border-t border-slate-100 align-top">
                        <td class="px-3 py-2">
                          <textarea class="input-base min-h-[70px] w-full" value={editQ()} onInput={(e) => setEditQ(e.currentTarget.value)} />
                        </td>
                        <td class="px-3 py-2">
                          <textarea class="input-base min-h-[90px] w-full" value={editA()} onInput={(e) => setEditA(e.currentTarget.value)} />
                        </td>
                        <td class="px-3 py-2">
                          <div class="flex gap-2">
                            <button class="rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-cyan-400" type="button" onClick={() => void saveEdit(record.question, editQ(), editA())}>
                              Save
                            </button>
                            <button class="rounded-md border border-rose-300 px-2 py-1 text-xs text-rose-700 hover:bg-rose-50" type="button" onClick={() => void removeRecord(record.question)}>
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  }}
                </For>
              </tbody>
            </table>
          </div>
        </Show>
      </Show>
    </section>
  )
}
