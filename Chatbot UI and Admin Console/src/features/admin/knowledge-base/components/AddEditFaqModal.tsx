import { useState } from 'react'
import { Check, Loader2, Plus, X } from 'lucide-react'

import type { KnowledgeBaseFaqRow } from '../viewmodel'
import type { EntryErrors, FaqEntryDraft } from './kb-types'
import { blankEntry, DEFAULT_CATEGORY } from './kb-types'
import { EntryForm } from './EntryForm'

export function AddEditFaqModal({
  initial,
  categories,
  saving,
  onSave,
  onClose,
}: {
  initial: KnowledgeBaseFaqRow | null
  categories: string[]
  saving: boolean
  onSave: (entries: Array<{ question: string; answer: string; category: string; tags: string[] }>) => void
  onClose: () => void
}) {
  const isEdit = Boolean(initial)

  const [entries, setEntries] = useState<FaqEntryDraft[]>(() =>
    initial
      ? [
          {
            question: initial.question,
            answer: initial.answer,
            category: initial.category,
            tags: initial.tags.join(', '),
            errors: {},
          },
        ]
      : [blankEntry(categories[0] || DEFAULT_CATEGORY)],
  )

  const handleChange = (idx: number, field: keyof FaqEntryDraft, value: string) => {
    setEntries((prev) =>
      prev.map((entry, index) =>
        index === idx
          ? {
              ...entry,
              [field]: value,
              errors: {
                ...entry.errors,
                ...(field === 'question' ? { q: '' } : {}),
                ...(field === 'answer' ? { a: '' } : {}),
              },
            }
          : entry,
      ),
    )
  }

  const handleRemove = (idx: number) => {
    setEntries((prev) => prev.filter((_, index) => index !== idx))
  }

  const handleAddAnother = () => {
    setEntries((prev) => [...prev, blankEntry(categories[0] || DEFAULT_CATEGORY)])
    setTimeout(() => {
      const el = document.getElementById('modal-scroll-area')
      if (el) el.scrollTop = el.scrollHeight
    }, 50)
  }

  const handleSave = () => {
    let hasError = false
    const validated = entries.map((entry) => {
      const errors: EntryErrors = {}
      if (!entry.question.trim()) {
        errors.q = 'Question is required'
        hasError = true
      }
      if (!entry.answer.trim()) {
        errors.a = 'Answer is required'
        hasError = true
      }
      return { ...entry, errors }
    })

    if (hasError) {
      setEntries(validated)
      return
    }

    onSave(
      entries.map((entry) => ({
        question: entry.question.trim(),
        answer: entry.answer.trim(),
        category: entry.category,
        tags: entry.tags.split(',').map((tag) => tag.trim()).filter(Boolean),
      })),
    )
  }

  const readyCount = entries.filter((entry) => entry.question.trim() && entry.answer.trim()).length

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-xl flex-col rounded-2xl border border-gray-100 bg-white shadow-2xl">
        <div className="flex shrink-0 items-center justify-between border-b border-gray-100 px-6 py-4">
          <div>
            <h2 className="text-base font-semibold text-gray-900">{isEdit ? 'Edit FAQ' : 'Add FAQs'}</h2>
            {!isEdit && entries.length > 1 && <p className="mt-0.5 text-xs text-gray-400">{entries.length} entries</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
            aria-label="Close dialog"
          >
            <X size={18} />
          </button>
        </div>

        <div id="modal-scroll-area" className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
          {entries.map((entry, index) => (
            <EntryForm
              key={`${entry.question}:${index}`}
              entry={entry}
              index={index}
              total={entries.length}
              categories={categories}
              onChange={handleChange}
              onRemove={handleRemove}
            />
          ))}

          {!isEdit && (
            <button
              type="button"
              onClick={handleAddAnother}
              className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-gray-200 py-3 text-sm text-gray-500 transition-all hover:border-teal-300 hover:bg-teal-50/30 hover:text-teal-600"
            >
              <Plus size={15} />
              Add another FAQ
            </button>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-between border-t border-gray-100 bg-gray-50/50 px-6 py-4">
          {!isEdit && entries.length > 1 ? (
            <p className="text-xs text-gray-400">
              {readyCount} of {entries.length} ready to save
            </p>
          ) : (
            <span />
          )}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg px-4 py-2 text-sm text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1.5 rounded-xl bg-teal-500 px-5 py-2 text-sm text-white shadow-sm transition-colors hover:bg-teal-600 disabled:opacity-50"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              {isEdit ? 'Save changes' : entries.length > 1 ? `Add ${entries.length} FAQs` : 'Add FAQ'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
