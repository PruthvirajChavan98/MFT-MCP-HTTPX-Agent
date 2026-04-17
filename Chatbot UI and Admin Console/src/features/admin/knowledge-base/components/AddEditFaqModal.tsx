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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-xl flex-col rounded-2xl border border-border bg-card shadow-2xl">
        <div className="flex shrink-0 items-center justify-between border-b border-border px-6 py-4">
          <div>
            <h2 className="text-base font-semibold text-foreground">{isEdit ? 'Edit FAQ' : 'Add FAQs'}</h2>
            {!isEdit && entries.length > 1 && (
              <p className="mt-0.5 text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">
                {entries.length} entries
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
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
              className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border py-3 text-sm text-muted-foreground transition-all hover:border-primary/40 hover:bg-primary/5 hover:text-primary"
            >
              <Plus size={15} />
              Add another FAQ
            </button>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-between border-t border-border bg-muted/30 px-6 py-4">
          {!isEdit && entries.length > 1 ? (
            <p className="text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">
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
              className="rounded-lg px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1.5 rounded-xl bg-primary px-5 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
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
