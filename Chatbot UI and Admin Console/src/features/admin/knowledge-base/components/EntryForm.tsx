import { AlertCircle, X } from 'lucide-react'

import type { FaqEntryDraft } from './kb-types'

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
    <div className="relative space-y-3 rounded-xl border border-gray-200 bg-gray-50/60 p-4">
      {total > 1 && (
        <div className="mb-1 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">FAQ #{index + 1}</span>
          <button
            type="button"
            onClick={() => onRemove(index)}
            className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500"
            aria-label="Remove this FAQ entry"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <div>
        <label className="mb-1.5 block text-xs font-medium text-gray-600">
          Question <span className="text-red-500">*</span>
        </label>
        <input
          value={entry.question}
          onChange={(event) => onChange(index, 'question', event.target.value)}
          placeholder="What does your customer need to know?"
          className={`w-full rounded-lg border px-3 py-2.5 text-sm text-gray-800 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-teal-400 ${entry.errors.q ? 'border-red-300' : 'border-gray-200'} bg-white`}
        />
        {entry.errors.q && (
          <p className="mt-1 flex items-center gap-1 text-xs text-red-500">
            <AlertCircle size={11} /> {entry.errors.q}
          </p>
        )}
      </div>

      <div>
        <label className="mb-1.5 block text-xs font-medium text-gray-600">
          Answer <span className="text-red-500">*</span>
        </label>
        <textarea
          value={entry.answer}
          onChange={(event) => onChange(index, 'answer', event.target.value)}
          placeholder="Provide a clear, concise answer."
          rows={3}
          className={`w-full resize-none rounded-lg border px-3 py-2.5 text-sm text-gray-800 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-teal-400 ${entry.errors.a ? 'border-red-300' : 'border-gray-200'} bg-white`}
        />
        {entry.errors.a && (
          <p className="mt-1 flex items-center gap-1 text-xs text-red-500">
            <AlertCircle size={11} /> {entry.errors.a}
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-xs font-medium text-gray-600">Category</label>
          <select
            value={entry.category}
            onChange={(event) => onChange(index, 'category', event.target.value)}
            className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-800 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-teal-400"
          >
            {categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium text-gray-600">
            Tags <span className="font-normal text-gray-400">(comma-separated)</span>
          </label>
          <input
            value={entry.tags}
            onChange={(event) => onChange(index, 'tags', event.target.value)}
            placeholder="e.g. billing, refund"
            className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-800 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-teal-400"
          />
        </div>
      </div>
    </div>
  )
}
