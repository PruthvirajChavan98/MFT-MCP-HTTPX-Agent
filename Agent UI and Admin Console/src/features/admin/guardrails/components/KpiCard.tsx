import {
  AlertTriangle,
  BarChart2,
  CheckCircle2,
  Clock,
  Layers,
  TrendingDown,
  type LucideIcon,
} from 'lucide-react'
import type { GuardrailKpiCard } from '../viewmodel'

const KPI_ICON_BY_LABEL: Record<string, LucideIcon> = {
  'Deny Rate': TrendingDown,
  'Avg Risk': AlertTriangle,
  'Queue Depth': Layers,
  'Oldest Queue Age': Clock,
  'Policy Adherence': CheckCircle2,
  'Total Evaluations': BarChart2,
}

const KPI_TONE_CLASSES: Record<
  GuardrailKpiCard['tone'],
  { panel: string; border: string; iconBackground: string; iconShadow: string }
> = {
  rose: {
    panel: 'from-rose-50 dark:from-rose-500/10',
    border: 'border-rose-100 dark:border-rose-500/30',
    iconBackground: 'bg-rose-500',
    iconShadow: 'shadow-rose-200',
  },
  amber: {
    panel: 'from-amber-50 dark:from-amber-500/10',
    border: 'border-amber-100 dark:border-amber-500/30',
    iconBackground: 'bg-amber-500',
    iconShadow: 'shadow-amber-200',
  },
  violet: {
    panel: 'from-violet-50 dark:from-violet-500/10',
    border: 'border-violet-100 dark:border-violet-500/30',
    iconBackground: 'bg-violet-500',
    iconShadow: 'shadow-violet-200',
  },
  sky: {
    panel: 'from-sky-50 dark:from-sky-500/10',
    border: 'border-sky-100 dark:border-sky-500/30',
    iconBackground: 'bg-sky-500',
    iconShadow: 'shadow-sky-200',
  },
  emerald: {
    panel: 'from-emerald-50 dark:from-emerald-500/10',
    border: 'border-emerald-100 dark:border-emerald-500/30',
    iconBackground: 'bg-emerald-500',
    iconShadow: 'shadow-emerald-200',
  },
  indigo: {
    panel: 'from-indigo-50 dark:from-indigo-500/10',
    border: 'border-indigo-100 dark:border-indigo-500/30',
    iconBackground: 'bg-indigo-500',
    iconShadow: 'shadow-indigo-200',
  },
}

export function KpiCard({ card }: { card: GuardrailKpiCard }) {
  const Icon = KPI_ICON_BY_LABEL[card.label] || BarChart2
  const tone = KPI_TONE_CLASSES[card.tone]

  return (
    <div className={`rounded-2xl border bg-gradient-to-br to-card p-4 shadow-sm ${tone.panel} ${tone.border}`}>
      <div className={`mb-3 inline-flex rounded-lg p-2 shadow-md ${tone.iconBackground} ${tone.iconShadow}`}>
        <Icon className="size-3.5 text-white" />
      </div>
      <p className="mb-1 text-[9px] font-bold uppercase leading-none tracking-[0.1em] text-muted-foreground">{card.label}</p>
      <p className="text-[22px] font-extrabold leading-none text-foreground">{card.value}</p>
    </div>
  )
}
