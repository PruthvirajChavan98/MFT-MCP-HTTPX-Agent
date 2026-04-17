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
      <span className="inline-flex items-center gap-1 rounded-full bg-[var(--success-soft)] px-2 py-0.5 text-[10px] font-tabular uppercase tracking-[0.15em] text-[var(--success)]">
        <span className="size-1.5 rounded-full bg-[var(--success)]" />
        Vectorized
      </span>
    )
  }

  if (vectorStatus === 'failed') {
    const label = vectorError ? vectorError.slice(0, 60) : 'Vectorization failed'
    return (
      <span
        className="inline-flex max-w-xs items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-tabular uppercase tracking-[0.15em] text-destructive"
        title={vectorError ?? undefined}
      >
        <span className="size-1.5 shrink-0 rounded-full bg-destructive" />
        <span className="truncate normal-case tracking-normal">
          {label}
          {vectorError && vectorError.length > 60 ? '…' : ''}
        </span>
      </span>
    )
  }

  if (vectorStatus === 'syncing') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-[var(--info-soft)] px-2 py-0.5 text-[10px] font-tabular uppercase tracking-[0.15em] text-[var(--info)]">
        <Loader2 className="size-3 animate-spin" />
        Syncing
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-[var(--warning-soft)] px-2 py-0.5 text-[10px] font-tabular uppercase tracking-[0.15em] text-[var(--warning)]">
      <span className="size-1.5 rounded-full bg-[var(--warning)]" />
      Pending
    </span>
  )
}
