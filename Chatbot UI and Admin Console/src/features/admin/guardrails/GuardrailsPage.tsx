import { Fragment, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Ban,
  BarChart2,
  CheckCircle2,
  ChevronsUpDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  MessageSquare,
  ShieldAlert,
} from 'lucide-react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import type { GuardrailEvent } from '@features/admin/api/admin'
import { buildConversationHref } from '@features/admin/lib/admin-links'
import { formatDateTime } from '@shared/lib/format'
import { Alert, AlertDescription } from '@components/ui/alert'
import { Input } from '@components/ui/input'
import { MobileHeader } from '@components/ui/mobile-header'
import { ResponsiveGrid } from '@components/ui/responsive-grid'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@components/ui/select'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@components/ui/sheet'
import { Skeleton } from '@components/ui/skeleton'
import {
  adminTraceQueryOptions,
  guardrailEventsQueryOptions,
  guardrailJudgeSummaryQueryOptions,
  guardrailQueueHealthQueryOptions,
  guardrailSummaryQueryOptions,
  guardrailTrendsQueryOptions,
} from '@features/admin/query/queryOptions'
import {
  extractInputTextFromTraceDetail,
  isBlockingDecision,
  mapGuardrailKpis,
  peakTrendValue,
  uniqueDecisionOptions,
} from './viewmodel'
import { TrendTooltip } from './components/TrendTooltip'
import { RiskBadge } from './components/RiskBadge'
import { DecisionBadge } from './components/DecisionBadge'
import { KpiCard } from './components/KpiCard'
import { FailureCard } from './components/FailureCard'
import { SortHeader, SORT_FIELD_TO_KEY, type SortField, type SortDir } from './components/SortHeader'

type TrendDatum = {
  bucket: string
  denied: number
  allowed: number
}

/**
 * Build a stable key for a guardrail event row.
 *
 * Must NOT depend on array index — the same event appears at different indices
 * depending on sort order (`sortedEvents` vs `events`) and filter-driven query
 * refetches, which previously caused the expanded-row state to silently drop
 * whenever a filter was applied.
 *
 * `session_id + event_time + trace_id` is the natural uniqueness tuple:
 * event_time is a high-resolution timestamp (microseconds on the backend),
 * two events on the same session at the same microsecond from the same trace
 * are effectively impossible.
 */
function buildEventKey(event: GuardrailEvent): string {
  return `${event.session_id}:${event.event_time}:${event.trace_id || ''}`
}

export function GuardrailsPage() {
  const [tenantId, setTenantId] = useState('default')
  const [decisionFilter, setDecisionFilter] = useState('all')
  const [hours, setHours] = useState('24')
  const [offset, setOffset] = useState(0)
  const [expandedEventKey, setExpandedEventKey] = useState<string | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<GuardrailEvent | null>(null)
  const [sortField, setSortField] = useState<SortField>('time')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const summaryQuery = useQuery(guardrailSummaryQueryOptions(tenantId))
  const queueQuery = useQuery(guardrailQueueHealthQueryOptions())
  const judgeQuery = useQuery(guardrailJudgeSummaryQueryOptions())
  const trendsQuery = useQuery(
    guardrailTrendsQueryOptions(tenantId, Number(hours)),
  )
  const eventsQuery = useQuery(
    guardrailEventsQueryOptions({
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

  const handleSort = (field: SortField) => {
    if (field === sortField) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir('desc')
    }
  }

  const sortedEvents = useMemo(() => {
    const key = SORT_FIELD_TO_KEY[sortField]
    return [...events].sort((a, b) => {
      const aVal = String(a[key] ?? '')
      const bVal = String(b[key] ?? '')
      const cmp = aVal.localeCompare(bVal, undefined, { numeric: true })
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [events, sortField, sortDir])

  const trendData = useMemo<TrendDatum[]>(() => {
    return (trendsQuery.data ?? []).map((item) => ({
      bucket: formatDateTime(item.bucket),
      denied: item.deny_events,
      allowed: Math.max(0, item.total_events - item.deny_events),
    }))
  }, [trendsQuery.data])

  const expandedEvent = useMemo(() => {
    if (!expandedEventKey) return null
    return events.find((event) => buildEventKey(event) === expandedEventKey) || null
  }, [events, expandedEventKey])

  useEffect(() => {
    if (!expandedEventKey) return
    if (expandedEvent) return
    setExpandedEventKey(null)
  }, [expandedEvent, expandedEventKey])

  const expandedTraceId = expandedEvent?.trace_id || null
  const expandedTraceQuery = useQuery(adminTraceQueryOptions(expandedTraceId))
  const expandedInput = extractInputTextFromTraceDetail(expandedTraceQuery.data)

  const kpiErrors = [summaryQuery.error, queueQuery.error, judgeQuery.error]
    .map((error) => (error as Error | undefined)?.message)
    .filter((message): message is string => Boolean(message))

  return (
    <div className="space-y-6 p-1">
      <MobileHeader
        title="Guardrails Observatory"
        description="Real-time policy enforcement monitoring"
        actions={
          <>
            <Input
              value={tenantId}
              onChange={(event) => {
                setOffset(0)
                setTenantId(event.target.value)
              }}
              placeholder="Tenant ID"
              className="h-9 w-full sm:w-40 text-xs"
            />
            <Select value={hours} onValueChange={setHours}>
              <SelectTrigger className="h-9 w-full sm:w-32 text-sm">
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
              <SelectTrigger className="h-9 w-full sm:w-44 text-sm">
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
          </>
        }
      />

      <ResponsiveGrid cols={{ base: 2, md: 3, xl: 6 }} gap={3}>
        {(summaryQuery.isLoading || queueQuery.isLoading || judgeQuery.isLoading)
          ? Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-28 rounded-2xl" />)
          : cards.map((card) => <KpiCard key={card.label} card={card} />)}
      </ResponsiveGrid>

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
                  <SortHeader label="Time" field="time" active={sortField === 'time'} dir={sortDir} onSort={handleSort} />
                  <SortHeader label="Session" field="session" active={sortField === 'session'} dir={sortDir} onSort={handleSort} />
                  <SortHeader label="Risk" field="risk" active={sortField === 'risk'} dir={sortDir} onSort={handleSort} />
                  <SortHeader label="Decision" field="decision" active={sortField === 'decision'} dir={sortDir} onSort={handleSort} />
                  <th className="hidden md:table-cell px-4 py-3 text-left text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort('path')}>
                    <span className="inline-flex items-center gap-1">
                      Path
                      {sortField === 'path'
                        ? (sortDir === 'asc' ? <ArrowUp size={10} /> : <ArrowDown size={10} />)
                        : <ChevronsUpDown size={10} className="opacity-30" />}
                    </span>
                  </th>
                  <th className="hidden lg:table-cell px-4 py-3 text-left text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground">Reasons</th>
                  <th className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground">Action</th>
                </tr>
              </thead>
              <tbody>
                {sortedEvents.map((event) => {
                  const key = buildEventKey(event)
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
                        <td className="hidden md:table-cell px-4 py-3.5">
                          <span className="rounded bg-muted px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
                            {event.request_path || '—'}
                          </span>
                        </td>
                        <td className="hidden lg:table-cell px-4 py-3.5">
                          <span className="rounded-full border border-violet-100 bg-violet-50 px-2.5 py-1 text-[11px] font-semibold text-violet-600 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-300">
                            {event.reasons.join(', ') || '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3.5 text-xs">
                          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-1.5">
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
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2 border-t border-border/60 px-6 py-3.5 text-xs text-muted-foreground">
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
