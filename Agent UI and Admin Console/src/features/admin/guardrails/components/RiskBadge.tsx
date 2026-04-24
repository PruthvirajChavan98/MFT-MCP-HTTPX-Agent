import { riskLevelFromScore } from '../viewmodel'

export function RiskBadge({ score }: { score: number }) {
  const level = riskLevelFromScore(score)
  const label = `${(score * 100).toFixed(0)}%`

  if (level === 'critical') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-100 px-2.5 py-1 text-[11px] font-bold text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
        <span className="inline-block size-1.5 rounded-full bg-red-500" /> Critical {label}
      </span>
    )
  }

  if (level === 'high') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-100 px-2.5 py-1 text-[11px] font-bold text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
        <span className="inline-block size-1.5 rounded-full bg-amber-500" /> High {label}
      </span>
    )
  }

  if (level === 'medium') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-violet-200 bg-violet-100 px-2.5 py-1 text-[11px] font-bold text-violet-700 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-300">
        <span className="inline-block size-1.5 rounded-full bg-violet-500" /> Medium {label}
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300">
      <span className="inline-block size-1.5 rounded-full bg-emerald-400" /> Low {label}
    </span>
  )
}
