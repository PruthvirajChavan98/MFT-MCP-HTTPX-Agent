import { Fragment, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import {
  AlertTriangle,
  BarChart2,
  Ban,
  CheckCheck,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  Layers,
  MessageSquare,
  ShieldAlert,
  TrendingDown,
  type LucideIcon,
} from 'lucide-react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  type TooltipContentProps,
} from 'recharts'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'
import {
  type GuardrailEvent,
  type GuardrailJudgeFailure,
} from '../../../../shared/api/admin'
import { buildConversationHref } from '../../../../shared/lib/admin-links'
import { formatDateTime } from '../../../../shared/lib/format'
import { Alert, AlertDescription } from '../../ui/alert'
import { Input } from '../../ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../ui/select'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../../ui/sheet'
import { Skeleton } from '../../ui/skeleton'
import { useAdminContext } from '../AdminContext'
import {
  adminTraceQueryOptions,
  guardrailEventsQueryOptions,
  guardrailJudgeSummaryQueryOptions,
  guardrailQueueHealthQueryOptions,
  guardrailSummaryQueryOptions,
  guardrailTrendsQueryOptions,
} from '../viewmodels/queryOptions'
import {
  extractInputTextFromTraceDetail,
  isBlockingDecision,
  mapGuardrailKpis,
  peakTrendValue,
  riskLevelFromScore,
  uniqueDecisionOptions,
  type GuardrailKpiCard,
  type GuardrailRiskLevel,
} from '../viewmodels/guardrails'

type TrendDatum = {
  bucket: string
  denied: number
  allowed: number
}

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

function buildEventKey(event: GuardrailEvent, index: number): string {
  return `${event.trace_id || 'trace'}:${event.event_time}:${index}`
}

function TrendTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
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

function RiskBadge({ score }: { score: number }) {
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

function DecisionBadge({ decision }: { decision: string }) {
  if (isBlockingDecision(decision)) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500 px-2.5 py-1 text-[11px] font-bold text-white">
        <Ban className="size-3" /> {decision}
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-500 px-2.5 py-1 text-[11px] font-bold text-white">
      <CheckCheck className="size-3" /> {decision}
    </span>
  )
}

function KpiCard({ card }: { card: GuardrailKpiCard }) {
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

function FailureCard({ failure }: { failure: GuardrailJudgeFailure }) {
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

export function GuardrailsEnterprise() {
  const [tenantId, setTenantId] = useState('default')
  const [decisionFilter, setDecisionFilter] = useState('all')
  const [hours, setHours] = useState('24')
  const [offset, setOffset] = useState(0)
  const [expandedEventKey, setExpandedEventKey] = useState<string | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<GuardrailEvent | null>(null)

  const adminContext = useAdminContext()

  const summaryQuery = useQuery(guardrailSummaryQueryOptions(adminContext.adminKey, tenantId))
  const queueQuery = useQuery(guardrailQueueHealthQueryOptions(adminContext.adminKey))
  const judgeQuery = useQuery(guardrailJudgeSummaryQueryOptions(adminContext.adminKey))
  const trendsQuery = useQuery(
    guardrailTrendsQueryOptions(adminContext.adminKey, tenantId, Number(hours)),
  )
  const eventsQuery = useQuery(
    guardrailEventsQueryOptions({
      adminKey: adminContext.adminKey,
      tenantId,
      decision: decisionFilter,
      offset,
      limit: 25,
    }),
  )

  const events = eventsQuery.data?.items ?? []
  const total = eventsQuery.data?.total ?? 0
  const hasNext = offset + events.length < total

  const cards = useMemo(
    () =>
      mapGuardrailKpis({
        summary: summaryQuery.data,
        queue: queueQuery.data,
        judge: judgeQuery.data,
      }),
    [summaryQuery.data, queueQuery.data, judgeQuery.data],
  )

  const decisionOptions = useMemo(() => uniqueDecisionOptions(events), [events])

  const trendData = useMemo<TrendDatum[]>(() => {
    return (trendsQuery.data ?? []).map((item) => ({
      bucket: formatDateTime(item.bucket),
      denied: item.deny_events,
      allowed: Math.max(0, item.total_events - item.deny_events),
    }))
  }, [trendsQuery.data])

  const expandedEvent = useMemo(() => {
    if (!expandedEventKey) return null
    return events.find((event, index) => buildEventKey(event, index) === expandedEventKey) || null
  }, [events, expandedEventKey])

  useEffect(() => {
    if (!expandedEventKey) return
    if (expandedEvent) return
    setExpandedEventKey(null)
  }, [expandedEvent, expandedEventKey])

  const expandedTraceId = expandedEvent?.trace_id || null
  const expandedTraceQuery = useQuery(adminTraceQueryOptions(adminContext.adminKey, expandedTraceId))
  const expandedInput = extractInputTextFromTraceDetail(expandedTraceQuery.data)

  const kpiErrors = [summaryQuery.error, queueQuery.error, judgeQuery.error]
    .map((error) => (error as Error | undefined)?.message)
    .filter((message): message is string => Boolean(message))

  if (!adminContext.adminKey) {
    return (
      <Alert>
        <AlertDescription>Set X-Admin-Key to view guardrail events.</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6 p-1">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-1 items-center gap-3">
          <div className="rounded-lg bg-rose-50 p-2 dark:bg-rose-500/10">
            <ShieldAlert className="size-5 text-rose-500" />
          </div>
          <div>
            <h1 className="text-[20px] font-bold leading-tight text-foreground">Guardrails Observatory</h1>
            <p className="text-xs text-muted-foreground">Real-time policy enforcement monitoring</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={tenantId}
            onChange={(event) => {
              setOffset(0)
              setTenantId(event.target.value)
            }}
            placeholder="Tenant ID"
            className="h-9 w-40 text-xs"
          />
          <Select value={hours} onValueChange={setHours}>
            <SelectTrigger className="h-9 w-32 text-sm">
              <Clock className="mr-1 size-3.5 text-muted-foreground" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="6">Last 6h</SelectItem>
              <SelectItem value="24">Last 24h</SelectItem>
              <SelectItem value="72">Last 72h</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={decisionFilter}
            onValueChange={(value) => {
              setOffset(0)
              setDecisionFilter(value)
            }}
          >
            <SelectTrigger className="h-9 w-44 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {decisionOptions.map((decision) => (
                <SelectItem key={decision} value={decision}>
                  {decision === 'all' ? 'All decisions' : decision}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {(summaryQuery.isLoading || queueQuery.isLoading || judgeQuery.isLoading)
          ? Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-28 rounded-2xl" />)
          : cards.map((card) => <KpiCard key={card.label} card={card} />)}
      </div>

      {!!kpiErrors.length && (
        <Alert variant="destructive">
          <AlertDescription>KPI data partially unavailable: {kpiErrors.join(' · ')}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
          <div className="flex items-center gap-2 border-b border-border/60 px-5 py-4">
            <BarChart2 className="size-4 text-rose-400" />
            <span className="text-sm font-semibold text-foreground">Decision Trend</span>
            <span className="ml-auto rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
              Peak {peakTrendValue(trendsQuery.data ?? [])}
            </span>
          </div>
          <div className="p-5">
            {trendsQuery.isLoading ? (
              <Skeleton className="h-48 rounded-lg" />
            ) : trendsQuery.error ? (
              <Alert variant="destructive">
                <AlertDescription>
                  Trend data unavailable: {(trendsQuery.error as Error).message}
                </AlertDescription>
              </Alert>
            ) : trendData.length ? (
              <div className="h-[190px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart accessibilityLayer data={trendData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }} barSize={14} barGap={4}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="bucket" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} dy={6} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} allowDecimals={false} />
                    <Tooltip cursor={{ fill: '#f8fafc' }} content={(props) => <TrendTooltip {...props} />} />
                    <Bar dataKey="denied" name="Denied" fill="#fb7185" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="allowed" name="Allowed" fill="#2dd4bf" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">No trend data available.</p>
            )}
          </div>
        </div>

        <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
          <div className="flex items-center gap-2 border-b border-border/60 px-5 py-4">
            <AlertTriangle className="size-4 text-amber-400" />
            <span className="text-sm font-semibold text-foreground">Recent Shadow Judge Failures</span>
            <span className="ml-auto rounded-full border border-amber-100 bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
              {(judgeQuery.data?.recent_failures ?? []).length} failures
            </span>
          </div>
          <div className="space-y-3 p-4">
            {judgeQuery.isLoading ? (
              Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-20 rounded-xl" />)
            ) : judgeQuery.data?.recent_failures?.length ? (
              judgeQuery.data.recent_failures.slice(0, 5).map((failure) => (
                <FailureCard key={`${failure.trace_id}-${failure.evaluated_at}`} failure={failure} />
              ))
            ) : (
              <div className="flex items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-muted/30 p-4">
                <CheckCircle2 className="size-4 text-emerald-400" />
                <p className="text-xs text-muted-foreground">No additional failures detected.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
        <div className="flex items-center gap-2 border-b border-border/60 px-6 py-4">
          <ShieldAlert className="size-4 text-muted-foreground" />
          <span className="text-sm font-semibold text-foreground">Events Log</span>
          <span className="ml-auto rounded-full bg-muted px-2.5 py-1 text-[11px] font-semibold text-muted-foreground">
            {events.length} events
          </span>
        </div>

        {eventsQuery.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-12 rounded" />
            ))}
          </div>
        ) : eventsQuery.error ? (
          <div className="p-4">
            <Alert variant="destructive">
              <AlertDescription>{(eventsQuery.error as Error).message}</AlertDescription>
            </Alert>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-muted/40">
                  <th className="w-8 px-4 py-3" />
                  {['Time', 'Session', 'Risk', 'Decision', 'Path', 'Reasons', 'Action'].map((header) => (
                    <th key={header} className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {events.map((event, index) => {
                  const key = buildEventKey(event, index)
                  const isExpanded = expandedEventKey === key

                  return (
                    <Fragment key={key}>
                      <tr className="border-t border-border/60 hover:bg-muted/30">
                        <td className="px-4 py-3.5">
                          <button
                            type="button"
                            aria-expanded={isExpanded}
                            aria-label={isExpanded ? 'Collapse row' : 'Expand row'}
                            className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                            onClick={() => setExpandedEventKey((prev) => (prev === key ? null : key))}
                          >
                            <ChevronRight className={`size-3.5 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                          </button>
                        </td>
                        <td className="whitespace-nowrap px-4 py-3.5 text-xs text-muted-foreground">
                          {formatDateTime(event.event_time)}
                        </td>
                        <td className="px-4 py-3.5">
                          <code className="rounded border border-sky-100 bg-sky-50 px-2 py-0.5 text-[11px] text-sky-600 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                            {event.session_id}
                          </code>
                        </td>
                        <td className="px-4 py-3.5">
                          <RiskBadge score={event.risk_score} />
                        </td>
                        <td className="px-4 py-3.5">
                          <DecisionBadge decision={event.risk_decision} />
                        </td>
                        <td className="px-4 py-3.5">
                          <span className="rounded bg-muted px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
                            {event.request_path || '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3.5">
                          <span className="rounded-full border border-violet-100 bg-violet-50 px-2.5 py-1 text-[11px] font-semibold text-violet-600 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-300">
                            {event.reasons.join(', ') || '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3.5 text-xs">
                          <div className="flex items-center gap-2">
                            {buildConversationHref(event.session_id) ? (
                              <Link
                                to={buildConversationHref(event.session_id)!}
                                className="inline-flex items-center rounded-lg border border-cyan-200 bg-cyan-50 px-2.5 py-1 font-semibold text-cyan-700 transition hover:bg-cyan-100 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-300 dark:hover:bg-cyan-500/20"
                              >
                                Conversation
                              </Link>
                            ) : (
                              <span className="text-muted-foreground">Unavailable</span>
                            )}
                            <button
                              type="button"
                              onClick={() => setSelectedEvent(event)}
                              className="rounded-lg border border-border px-2.5 py-1 font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground"
                            >
                              Details
                            </button>
                          </div>
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr key={`${key}-expanded`} className="border-t border-border/60 bg-muted/20">
                          <td colSpan={8} className="px-6 py-4">
                            <div className={`rounded-xl border p-4 ${isBlockingDecision(event.risk_decision) ? 'border-rose-200 bg-rose-50/60 dark:border-rose-500/30 dark:bg-rose-500/10' : 'border-border bg-card'}`}>
                              <div className="mb-3 flex items-center gap-2">
                                <MessageSquare className={`size-3.5 ${isBlockingDecision(event.risk_decision) ? 'text-rose-400' : 'text-muted-foreground'}`} />
                                <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground">Triggering Input</span>
                                {isBlockingDecision(event.risk_decision) && (
                                  <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-rose-500 px-2 py-0.5 text-[10px] font-bold text-white">
                                    <Ban className="size-2.5" /> Blocked by policy
                                  </span>
                                )}
                              </div>

                              {!event.trace_id ? (
                                <p className="text-xs text-muted-foreground">Trace ID unavailable for this event.</p>
                              ) : expandedTraceQuery.isLoading ? (
                                <Skeleton className="h-14 rounded-lg" />
                              ) : expandedTraceQuery.error ? (
                                <Alert variant="destructive">
                                  <AlertDescription>
                                    Failed to load trace input: {(expandedTraceQuery.error as Error).message}
                                  </AlertDescription>
                                </Alert>
                              ) : (
                                <div className={`rounded-lg px-4 py-3 font-mono text-[13px] ${isBlockingDecision(event.risk_decision) ? 'bg-gray-950 text-rose-300' : 'bg-gray-900 text-emerald-300'}`}>
                                  {expandedInput || 'No prompt text captured for this trace.'}
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}

                {!events.length && (
                  <tr>
                    <td colSpan={8} className="px-6 py-8 text-center text-sm text-muted-foreground">
                      No events available.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {!eventsQuery.error && (
          <div className="flex items-center justify-between border-t border-border/60 px-6 py-3.5 text-xs text-muted-foreground">
            <p>
              Showing {total ? offset + 1 : 0}-{Math.min(offset + events.length, total)} of {total} events
            </p>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 transition-colors hover:border-muted-foreground/30 hover:text-foreground disabled:opacity-50"
                disabled={offset === 0}
                onClick={() => setOffset((prev) => Math.max(0, prev - 25))}
              >
                <ChevronLeft className="size-3.5" /> Previous
              </button>
              <button
                type="button"
                className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 transition-colors hover:border-muted-foreground/30 hover:text-foreground disabled:opacity-50"
                disabled={!hasNext}
                onClick={() => setOffset((prev) => prev + 25)}
              >
                Next <ChevronRight className="size-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      <Sheet open={Boolean(selectedEvent)} onOpenChange={() => setSelectedEvent(null)}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle className="text-sm">Guardrail Event Detail</SheetTitle>
          </SheetHeader>
          {selectedEvent && (
            <div className="mt-4 space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2">
                {[
                  ['Time', formatDateTime(selectedEvent.event_time)],
                  ['Session', selectedEvent.session_id],
                  ['Decision', selectedEvent.risk_decision],
                  ['Path', selectedEvent.request_path || '—'],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg border border-border bg-muted/40 p-2">
                    <p className="text-[10px] font-semibold uppercase text-muted-foreground">{label}</p>
                    <p className="mt-0.5 truncate font-mono text-xs text-foreground">{value}</p>
                  </div>
                ))}
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold text-muted-foreground">Risk Score</p>
                <RiskBadge score={selectedEvent.risk_score} />
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold text-muted-foreground">Reasons</p>
                <ul className="space-y-1">
                  {selectedEvent.reasons.map((reason) => (
                    <li key={reason} className="flex items-start gap-2 text-xs">
                      <AlertTriangle size={12} className="mt-0.5 shrink-0 text-amber-500" />
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}
