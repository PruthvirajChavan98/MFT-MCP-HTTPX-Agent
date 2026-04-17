import { memo, type ComponentType } from 'react'
import type { LucideProps } from 'lucide-react'

import { Card } from '@components/ui/card'

export type StatTone = 'default' | 'success' | 'warning' | 'info' | 'destructive'

export interface StatCardProps {
  label: string
  value: string | number
  icon?: ComponentType<LucideProps>
  tone?: StatTone
  /** Optional sub-line (e.g. delta, range). Renders small, below the value. */
  hint?: string
}

const toneClasses: Record<StatTone, { icon: string; accent: string }> = {
  default: {
    icon: 'bg-muted text-muted-foreground',
    accent: '',
  },
  success: {
    icon: 'bg-[var(--success-soft)] text-[var(--success)]',
    accent: '',
  },
  warning: {
    icon: 'bg-[var(--warning-soft)] text-[var(--warning)]',
    accent: '',
  },
  info: {
    icon: 'bg-[var(--info-soft)] text-[var(--info)]',
    accent: '',
  },
  destructive: {
    icon: 'bg-destructive/10 text-destructive',
    accent: '',
  },
}

/**
 * StatCard — the Terminal-grade Fintech numeric readout card.
 *
 * Uses the monospace tabular font for the value so digits align column-wise
 * across a grid of StatCards. Memoised because it's rendered in grids that
 * refresh on 30 s polling cycles — `React.memo` shaves unnecessary re-renders
 * when neither the label nor the value actually changed.
 */
function StatCardImpl({ label, value, icon: Icon, tone = 'default', hint }: StatCardProps) {
  const tones = toneClasses[tone]
  return (
    <Card
      variant="bordered"
      className="p-5 flex flex-col gap-3 transition-colors hover:bg-accent/40"
    >
      <div className="flex items-center justify-between">
        {Icon ? (
          <div
            className={`size-9 rounded-md flex items-center justify-center ${tones.icon}`}
            aria-hidden
          >
            <Icon className="size-4" />
          </div>
        ) : (
          <span className="size-9" aria-hidden />
        )}
        <span className="text-[10px] font-tabular uppercase tracking-[0.18em] text-muted-foreground">
          {label}
        </span>
      </div>
      <div>
        <div className="font-tabular text-3xl font-medium tracking-tight text-foreground leading-none">
          {value}
        </div>
        {hint ? (
          <div className="mt-1.5 text-xs text-muted-foreground">{hint}</div>
        ) : null}
      </div>
    </Card>
  )
}

export const StatCard = memo(StatCardImpl)
