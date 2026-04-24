import { AlertTriangle } from 'lucide-react'
import type { GuardrailJudgeFailure } from '@features/admin/api/admin'

export function FailureCard({ failure }: { failure: GuardrailJudgeFailure }) {
  return (
    <div className="rounded-xl border border-rose-100 bg-rose-50/40 p-4 dark:border-rose-500/30 dark:bg-rose-500/10">
      <div className="mb-2 flex items-start justify-between gap-3">
        <code className="break-all rounded border border-sky-100 bg-sky-50 px-2 py-0.5 text-[11px] text-sky-600 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
          {failure.trace_id}
        </code>
        <span className="shrink-0 whitespace-nowrap rounded-full bg-rose-500 px-2.5 py-1 text-[10px] font-bold text-white">
          Policy {(failure.policy_adherence * 100).toFixed(0)}%
        </span>
      </div>
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-amber-500" />
        <p className="text-xs text-muted-foreground">{failure.summary || 'No summary provided.'}</p>
      </div>
    </div>
  )
}
