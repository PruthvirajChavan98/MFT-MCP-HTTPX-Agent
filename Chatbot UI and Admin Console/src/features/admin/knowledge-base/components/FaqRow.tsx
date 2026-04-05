import { useState } from 'react'
import {
  ChevronDown,
  ChevronUp,
  Copy,
  MoreHorizontal,
  Pencil,
  Tag,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'

import { formatDateTime } from '@shared/lib/format'
import type { KnowledgeBaseFaqRow } from '../viewmodel'
import { StatusBadge } from './StatusBadge'
import { CategoryBadge } from './CategoryBadge'

export function FAQRow({
  faq,
  onEdit,
  onDelete,
}: {
  faq: KnowledgeBaseFaqRow
  onEdit: (row: KnowledgeBaseFaqRow) => void
  onDelete: (row: KnowledgeBaseFaqRow) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  const toggleExpanded = () => setExpanded((prev) => !prev)

  return (
    <div className="mb-2 rounded-xl border border-gray-100 bg-white shadow-sm transition-shadow duration-200 hover:shadow-md">
      <div
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        onClick={toggleExpanded}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            toggleExpanded()
          }
        }}
        className="flex cursor-pointer items-start gap-4 px-3 sm:px-5 py-3 sm:py-4"
      >
        <button
          type="button"
          className="mt-0.5 shrink-0 text-gray-400 transition-colors hover:text-gray-600"
          aria-label={expanded ? 'Collapse FAQ row' : 'Expand FAQ row'}
          onClick={(event) => {
            event.stopPropagation()
            toggleExpanded()
          }}
        >
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>

        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-gray-800">{faq.question}</p>
          {!expanded && <p className="mt-0.5 truncate text-xs text-gray-400">{faq.answer}</p>}
        </div>

        <div
          className="flex flex-col sm:flex-row shrink-0 items-end sm:items-center gap-1.5 sm:gap-2"
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
        >
          <CategoryBadge category={faq.category} />
          <StatusBadge vectorStatus={faq.vectorStatus} vectorError={faq.vectorError} />
          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((prev) => !prev)}
              aria-expanded={menuOpen}
              aria-label="Open row actions"
              className="rounded-lg p-1.5 text-gray-400 transition-all hover:bg-gray-100 hover:text-gray-700"
            >
              <MoreHorizontal size={16} />
            </button>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} aria-hidden />
                <div className="absolute right-0 top-8 z-20 w-36 overflow-hidden rounded-xl border border-gray-100 bg-white py-1 shadow-xl">
                  <button
                    type="button"
                    onClick={() => {
                      onEdit(faq)
                      setMenuOpen(false)
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
                  >
                    <Pencil size={13} />
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      await navigator.clipboard.writeText(`Q: ${faq.question}\nA: ${faq.answer}`)
                      toast.success('Copied to clipboard')
                      setMenuOpen(false)
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
                  >
                    <Copy size={13} />
                    Copy
                  </button>
                  <div className="my-1 border-t border-gray-100" />
                  <button
                    type="button"
                    onClick={() => {
                      onDelete(faq)
                      setMenuOpen(false)
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-600 transition-colors hover:bg-red-50"
                  >
                    <Trash2 size={13} />
                    Delete
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-50 bg-gray-50/50 px-3 sm:px-5 py-3 sm:py-4">
          <p className="mb-3 text-sm leading-relaxed text-gray-600">{faq.answer}</p>
          <div className="flex flex-wrap items-center gap-2">
            {faq.tags.map((tag) => (
              <span key={tag} className="inline-flex items-center gap-1 rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                <Tag size={10} />
                {tag}
              </span>
            ))}
            <span className="ml-auto text-xs text-gray-400">
              Added {faq.createdAt ? formatDateTime(faq.createdAt) : '—'}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
