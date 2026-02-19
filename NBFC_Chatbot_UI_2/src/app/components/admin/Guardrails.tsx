import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ShieldAlert, ShieldCheck, ShieldX } from 'lucide-react'
import { fetchGuardrailEvents } from '../../../shared/api/admin'
import { useAdminContext } from './AdminContext'
import { Card, CardContent } from '../ui/card'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { Badge } from '../ui/badge'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../ui/sheet'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import { formatDateTime } from '../../../shared/lib/format'
import type { GuardrailEvent } from '../../../shared/api/admin'

function RiskBadge({ score }: { score: number }) {
  if (score >= 0.8) return <Badge variant="destructive" className="text-[10px]">Critical {(score * 100).toFixed(0)}%</Badge>
  if (score >= 0.5) return <Badge className="text-[10px] bg-orange-500">High {(score * 100).toFixed(0)}%</Badge>
  if (score >= 0.3) return <Badge variant="secondary" className="text-[10px]">Medium {(score * 100).toFixed(0)}%</Badge>
  return <Badge variant="outline" className="text-[10px]">Low {(score * 100).toFixed(0)}%</Badge>
}

function DecisionBadge({ decision }: { decision: string }) {
  const lower = decision?.toLowerCase() ?? ''
  if (lower.includes('block')) return <Badge variant="destructive" className="text-[10px]"><ShieldX size={10} className="mr-1" />{decision}</Badge>
  if (lower.includes('allow')) return <Badge className="text-[10px] bg-emerald-500"><ShieldCheck size={10} className="mr-1" />{decision}</Badge>
  return <Badge variant="outline" className="text-[10px]"><ShieldAlert size={10} className="mr-1" />{decision}</Badge>
}

export function Guardrails() {
  const auth = useAdminContext()
  const [decisionFilter, setDecisionFilter] = useState('all')
  const [selected, setSelected] = useState<GuardrailEvent | null>(null)

  const { data = [], isLoading, error } = useQuery({
    queryKey: ['guardrail-events', auth.adminKey],
    queryFn: () => fetchGuardrailEvents(auth.adminKey),
    enabled: !!auth.adminKey,
  })

  if (!auth.adminKey) return <Alert><AlertDescription>Set X-Admin-Key to view guardrail events.</AlertDescription></Alert>
  if (error) return <Alert variant="destructive"><AlertDescription>{(error as Error).message}</AlertDescription></Alert>

  const decisions = ['all', ...new Set(data.map((e) => e.risk_decision).filter(Boolean))]
  const filtered = decisionFilter === 'all' ? data : data.filter((e) => e.risk_decision === decisionFilter)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h1 className="text-xl font-semibold">Guardrails</h1>
        <Select value={decisionFilter} onValueChange={setDecisionFilter}>
          <SelectTrigger className="w-40 h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>{decisions.map((d) => <SelectItem key={d} value={d}>{d === 'all' ? 'All decisions' : d}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? <div className="p-4 space-y-2">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12 rounded" />)}</div> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b">
                  <tr>{['Time', 'Session', 'Risk', 'Decision', 'Path', 'Reasons'].map((h) => <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">{h}</th>)}</tr>
                </thead>
                <tbody>
                  {filtered.map((ev, i) => (
                    <tr key={i} className="border-b last:border-0 hover:bg-slate-50/50 cursor-pointer" onClick={() => setSelected(ev)}>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{formatDateTime(ev.event_time)}</td>
                      <td className="px-4 py-2.5 font-mono text-xs text-slate-500 max-w-[120px] truncate">{ev.session_id}</td>
                      <td className="px-4 py-2.5"><RiskBadge score={ev.risk_score} /></td>
                      <td className="px-4 py-2.5"><DecisionBadge decision={ev.risk_decision} /></td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-[120px] truncate">{ev.request_path ?? '—'}</td>
                      <td className="px-4 py-2.5 text-xs max-w-[200px] truncate">{ev.reasons.join(', ')}</td>
                    </tr>
                  ))}
                  {!filtered.length && <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-muted-foreground">No events</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Sheet open={!!selected} onOpenChange={() => setSelected(null)}>
        <SheetContent>
          <SheetHeader><SheetTitle className="text-sm">Guardrail Event Detail</SheetTitle></SheetHeader>
          {selected && (
            <div className="mt-4 space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2">
                {[
                  ['Time', formatDateTime(selected.event_time)],
                  ['Session', selected.session_id],
                  ['Decision', selected.risk_decision],
                  ['Path', selected.request_path ?? '—'],
                ].map(([k, v]) => (
                  <div key={k} className="bg-slate-50 rounded-lg p-2 border border-slate-100">
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase">{k}</p>
                    <p className="text-xs font-mono text-slate-700 truncate mt-0.5">{v}</p>
                  </div>
                ))}
              </div>
              <div><p className="text-xs font-semibold text-muted-foreground mb-1">Risk Score</p><RiskBadge score={selected.risk_score} /></div>
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">Reasons</p>
                <ul className="space-y-1">{selected.reasons.map((r, i) => <li key={i} className="flex items-start gap-2 text-xs"><AlertTriangle size={12} className="text-amber-500 mt-0.5 shrink-0" />{r}</li>)}</ul>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}
