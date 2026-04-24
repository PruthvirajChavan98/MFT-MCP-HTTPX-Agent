import { AlertCircle, X } from 'lucide-react'

import type { FaqEntryDraft } from './kb-types'

const INPUT_BASE =
  'w-full rounded-md border bg-background px-3 py-2.5 text-sm text-foreground transition-colors placeholder:text-muted-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/30'
const LABEL_BASE = 'mb-1.5 block text-[11px] font-tabular uppercase tracking-[0.15em] text-muted-foreground'

export function EntryForm({
  entry,
  index,
  total,
  categories,
  onChange,
  onRemove,
}: {
  entry: FaqEntryDraft
  index: number
  total: number
  categories: string[]
  onChange: (idx: number, field: keyof FaqEntryDraft, value: string) => void
  onRemove: (idx: number) => void
}) {
  return (
    <div className="relative space-y-3 rounded-md border border-border bg-muted/30 p-4">
      {total > 1 && (
        <div className="mb-1 flex items-center justify-between">
          <span className="text-[11px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">
            FAQ #{index + 1}
          </span>
          <button
            type="button"
            onClick={() => onRemove(index)}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
            aria-label="Remove this FAQ entry"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <div>
        <label className={LABEL_BASE}>
          Question <span className="text-destructive">*</span>
        </label>
        <input
          value={entry.question}
          onChange={(event) => onChange(index, 'question', event.target.value)}
          placeholder="What does your customer need to know?"
          className={`${INPUT_BASE} ${entry.errors.q ? 'border-destructive/60' : 'border-border'}`}
        />
        {entry.errors.q && (
          <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
            <AlertCircle size={11} /> {entry.errors.q}
          </p>
        )}
      </div>

      <div>
        <label className={LABEL_BASE}>
          Answer <span className="text-destructive">*</span>
        </label>
        <textarea
          value={entry.answer}
          onChange={(event) => onChange(index, 'answer', event.target.value)}
          placeholder="Provide a clear, concise answer."
          rows={3}
          className={`${INPUT_BASE} resize-none ${entry.errors.a ? 'border-destructive/60' : 'border-border'}`}
        />
        {entry.errors.a && (
          <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
            <AlertCircle size={11} /> {entry.errors.a}
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className={LABEL_BASE}>Category</label>
          <select
            value={entry.category}
            onChange={(event) => onChange(index, 'category', event.target.value)}
            className={`${INPUT_BASE} border-border`}
          >
            {categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={LABEL_BASE}>
            Tags <span className="font-normal normal-case tracking-normal text-muted-foreground/70">(comma-separated)</span>
          </label>
          <input
            value={entry.tags}
            onChange={(event) => onChange(index, 'tags', event.target.value)}
            placeholder="e.g. billing, refund"
            className={`${INPUT_BASE} border-border`}
          />
        </div>
      </div>
    </div>
  )
}
