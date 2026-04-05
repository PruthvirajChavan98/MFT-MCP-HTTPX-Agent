import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react'
import type { GuardrailEvent } from '@features/admin/api/admin'

export type SortField = 'time' | 'session' | 'risk' | 'decision' | 'path'
export type SortDir = 'asc' | 'desc'

export const SORT_FIELD_TO_KEY: Record<SortField, keyof GuardrailEvent> = {
  time: 'event_time',
  session: 'session_id',
  risk: 'risk_score',
  decision: 'risk_decision',
  path: 'request_path',
}

export function SortHeader({
  label,
  field,
  active,
  dir,
  onSort,
}: {
  label: string
  field: SortField
  active: boolean
  dir: SortDir
  onSort: (field: SortField) => void
}) {
  return (
    <th
      className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground cursor-pointer select-none hover:text-foreground transition-colors"
      onClick={() => onSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active
          ? (dir === 'asc' ? <ArrowUp size={10} /> : <ArrowDown size={10} />)
          : <ChevronsUpDown size={10} className="opacity-30" />}
      </span>
    </th>
  )
}
