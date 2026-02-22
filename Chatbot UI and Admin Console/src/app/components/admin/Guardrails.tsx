import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ShieldAlert, ShieldCheck, ShieldX } from 'lucide-react'
import {
  fetchGuardrailEvents,
  fetchGuardrailJudgeSummary,
  fetchGuardrailQueueHealth,
  fetchGuardrailSummary,
  fetchGuardrailTrends,
} from '../../../shared/api/admin'
import { useAdminContext } from './AdminContext'
import { Card, CardContent } from '../ui/card'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { Badge } from '../ui/badge'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../ui/sheet'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import { Input } from '../ui/input'
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
  const [tenantId, setTenantId] = useState('default')
  const [decisionFilter, setDecisionFilter] = useState('all')
  const [hours, setHours] = useState('24')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<GuardrailEvent | null>(null)

  const { data: summary, isLoading: summaryLoading, error: summaryError } = useQuery({
    queryKey: ['guardrail-summary', auth.adminKey, tenantId],
    queryFn: () => fetchGuardrailSummary(auth.adminKey, tenantId),
    enabled: !!auth.adminKey && !!tenantId.trim(),
    refetchInterval: 30_000,
  })

  const { data: queueHealth, isLoading: queueLoading, error: queueError } = useQuery({
    queryKey: ['guardrail-queue', auth.adminKey],
    queryFn: () => fetchGuardrailQueueHealth(auth.adminKey),
    enabled: !!auth.adminKey,
    refetchInterval: 10_000,
  })

  const { data: judgeSummary, isLoading: judgeLoading, error: judgeError } = useQuery({
    queryKey: ['guardrail-judge', auth.adminKey],
    queryFn: () => fetchGuardrailJudgeSummary(auth.adminKey),
    enabled: !!auth.adminKey,
    refetchInterval: 30_000,
  })

  const { data: trends = [], isLoading: trendsLoading, error: trendsError } = useQuery({
    queryKey: ['guardrail-trends', auth.adminKey, tenantId, hours],
    queryFn: () => fetchGuardrailTrends(auth.adminKey, tenantId, Number(hours)),
    enabled: !!auth.adminKey && !!tenantId.trim(),
    refetchInterval: 30_000,
  })

  const { data: eventsResponse, isLoading, error } = useQuery({
    queryKey: ['guardrail-events', auth.adminKey, tenantId, decisionFilter, offset],
    queryFn: () =>
      fetchGuardrailEvents(auth.adminKey, {
        tenantId,
        decision: decisionFilter,
        offset,
        limit: 25,
      }),
    enabled: !!auth.adminKey,
  })

  const data = eventsResponse?.items ?? []
  const total = eventsResponse?.total ?? 0
  const hasNext = offset + data.length < total

  if (!auth.adminKey) return <Alert><AlertDescription>Set X-Admin-Key to view guardrail events.</AlertDescription></Alert>
  if (error || summaryError || queueError || judgeError || trendsError) {
    const message =
      (error as Error | undefined)?.message ||
      (summaryError as Error | undefined)?.message ||
      (queueError as Error | undefined)?.message ||
      (judgeError as Error | undefined)?.message ||
      (trendsError as Error | undefined)?.message ||
      'Failed to load guardrails data.'
    return <Alert variant="destructive"><AlertDescription>{message}</AlertDescription></Alert>
  }

  const decisions = ['all', ...new Set(data.map((e) => e.risk_decision).filter(Boolean))]
  const trendPeak = useMemo(() => Math.max(...trends.map((item) => item.total_events), 1), [trends])

  const cards = [
    { label: 'Deny Rate', value: `${((summary?.deny_rate ?? 0) * 100).toFixed(1)}%` },
    { label: 'Avg Risk', value: `${((summary?.avg_risk_score ?? 0) * 100).toFixed(0)}%` },
    { label: 'Queue Depth', value: queueHealth?.depth?.toString() ?? '0' },
    { label: 'Oldest Queue Age', value: queueHealth?.oldest_age_seconds ? `${queueHealth.oldest_age_seconds}s` : '0s' },
    { label: 'Policy Adherence', value: `${((judgeSummary?.avg_policy_adherence ?? 0) * 100).toFixed(1)}%` },
    { label: 'Total Evaluations', value: judgeSummary?.total_evals?.toString() ?? '0' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h1 className="text-xl font-semibold">Guardrails Observatory</h1>
        <div className="flex items-center gap-2 flex-wrap">
          <Input
            value={tenantId}
            onChange={(event) => setTenantId(event.target.value)}
            placeholder="Tenant ID"
            className="h-8 w-36 text-xs"
          />
          <Select value={hours} onValueChange={setHours}>
            <SelectTrigger className="w-28 h-8 text-sm"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="6">Last 6h</SelectItem>
              <SelectItem value="24">Last 24h</SelectItem>
              <SelectItem value="72">Last 72h</SelectItem>
            </SelectContent>
          </Select>
          <Select value={decisionFilter} onValueChange={(value) => { setOffset(0); setDecisionFilter(value) }}>
            <SelectTrigger className="w-40 h-8 text-sm"><SelectValue /></SelectTrigger>
            <SelectContent>{decisions.map((d) => <SelectItem key={d} value={d}>{d === 'all' ? 'All decisions' : d}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-6 gap-3">
        {(summaryLoading || queueLoading || judgeLoading)
          ? Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-20 rounded-lg" />)
          : cards.map((card) => (
              <Card key={card.label}>
                <CardContent className="pt-5">
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{card.label}</p>
                  <p className="text-xl font-semibold mt-1">{card.value}</p>
                </CardContent>
              </Card>
            ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="pt-5 space-y-3">
            <h2 className="text-sm font-semibold">Decision Trend</h2>
            {trendsLoading ? (
              <Skeleton className="h-48 rounded-lg" />
            ) : (
              <div className="space-y-2">
                {trends.map((item) => (
                  <div key={item.bucket} className="space-y-1">
                    <div className="flex justify-between text-[11px] text-muted-foreground">
                      <span>{formatDateTime(item.bucket)}</span>
                      <span>{item.deny_events}/{item.total_events} denied</span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-rose-400"
                        style={{ width: `${Math.max(4, (item.total_events / trendPeak) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
                {!trends.length && <p className="text-xs text-muted-foreground">No trend data available.</p>}
              </div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5 space-y-3">
            <h2 className="text-sm font-semibold">Recent Shadow Judge Failures</h2>
            {judgeLoading ? (
              <Skeleton className="h-48 rounded-lg" />
            ) : (
              <div className="space-y-2">
                {(judgeSummary?.recent_failures ?? []).slice(0, 5).map((failure) => (
                  <div key={`${failure.trace_id}-${failure.evaluated_at}`} className="border rounded-lg p-2.5 text-xs space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-slate-500 truncate">{failure.trace_id}</span>
                      <Badge variant="destructive">Policy {(failure.policy_adherence * 100).toFixed(0)}%</Badge>
                    </div>
                    <p className="text-muted-foreground line-clamp-2">{failure.summary || 'No summary provided.'}</p>
                  </div>
                ))}
                {!judgeSummary?.recent_failures?.length && (
                  <p className="text-xs text-muted-foreground">No recent failures.</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
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
                  {data.map((ev, i) => (
                    <tr key={i} className="border-b last:border-0 hover:bg-slate-50/50 cursor-pointer" onClick={() => setSelected(ev)}>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{formatDateTime(ev.event_time)}</td>
                      <td className="px-4 py-2.5 font-mono text-xs text-slate-500 max-w-[120px] truncate">{ev.session_id}</td>
                      <td className="px-4 py-2.5"><RiskBadge score={ev.risk_score} /></td>
                      <td className="px-4 py-2.5"><DecisionBadge decision={ev.risk_decision} /></td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-[120px] truncate">{ev.request_path ?? '—'}</td>
                      <td className="px-4 py-2.5 text-xs max-w-[200px] truncate">{ev.reasons.join(', ')}</td>
                    </tr>
                  ))}
                  {!data.length && <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-muted-foreground">No events</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          Showing {offset + 1}-{Math.min(offset + data.length, total)} of {total} events
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            className="px-2.5 py-1 rounded border disabled:opacity-50"
            disabled={offset === 0}
            onClick={() => setOffset((prev) => Math.max(0, prev - 25))}
          >
            Previous
          </button>
          <button
            type="button"
            className="px-2.5 py-1 rounded border disabled:opacity-50"
            disabled={!hasNext}
            onClick={() => setOffset((prev) => prev + 25)}
          >
            Next
          </button>
        </div>
      </div>

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
