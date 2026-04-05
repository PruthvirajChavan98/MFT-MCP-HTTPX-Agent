import { Loader2 } from 'lucide-react'

import type { KnowledgeBaseFaqRow } from '../viewmodel'

export function StatusBadge({
  vectorStatus,
  vectorError,
}: {
  vectorStatus: KnowledgeBaseFaqRow['vectorStatus']
  vectorError: KnowledgeBaseFaqRow['vectorError']
}) {
  if (vectorStatus === 'synced') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-teal-200 bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-700">
        <span className="h-1.5 w-1.5 rounded-full bg-teal-500" />
        Vectorized
      </span>
    )
  }

  if (vectorStatus === 'failed') {
    const label = vectorError ? vectorError.slice(0, 60) : 'Vectorization failed'
    return (
      <span
        className="inline-flex max-w-xs items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700"
        title={vectorError ?? undefined}
      >
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-rose-500" />
        <span className="truncate">{label}{vectorError && vectorError.length > 60 ? '…' : ''}</span>
      </span>
    )
  }

  if (vectorStatus === 'syncing') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-700">
        <Loader2 className="size-3 animate-spin" />
        Syncing
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
      Pending
    </span>
  )
}
