import type { TooltipContentProps } from 'recharts'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'

export function TrendTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null

  return (
    <div className="rounded-xl border border-border bg-card p-3 shadow-lg">
      <p className="mb-1 text-[11px] text-muted-foreground">{String(label || '')}</p>
      {payload.map((entry, index) => (
        <p key={`${String(entry.name)}-${index}`} style={{ color: entry.color || '#64748b' }} className="text-xs font-semibold">
          {String(entry.name)}: {Number(entry.value ?? 0)}
        </p>
      ))}
    </div>
  )
}
