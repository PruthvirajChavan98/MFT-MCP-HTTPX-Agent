import { lazy, Suspense, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Activity, Clock, DollarSign, MessageSquare, Shield, Users } from 'lucide-react'

import {
  fetchEvalTraces,
  fetchGuardrailEvents,
  fetchQuestionTypes,
  fetchSessionCostSummary,
} from '@features/admin/api/admin'
import { Alert, AlertDescription } from '@components/ui/alert'
import { Skeleton } from '@components/ui/skeleton'
import { ResponsiveGrid } from '@components/ui/responsive-grid'
import { ResponsiveTable, type Column } from '@components/ui/responsive-table'
import { MobileHeader } from '@components/ui/mobile-header'
import { Card } from '@components/ui/card'
import { StatCard } from '@features/admin/components/StatCard'
import { usePersistedGranularity } from '@features/admin/components/GranularityTabs'
import { trailingBuckets } from '@features/admin/lib/time-bucket'
import { formatCurrency, formatDateTime } from '@shared/lib/format'
import { buildConversationHref, buildTraceHref } from '@features/admin/lib/admin-links'
import { isBlockingDecision } from '@features/admin/guardrails/viewmodel'
import type { EvalTraceSummary } from '@features/admin/types/admin'

// Lazy-load recharts via a page-scoped child. Shaves ~370 KB off the initial
// admin bundle (vercel-react-best-practices: bundle-dynamic-imports).
const DashboardCharts = lazy(() => import('./DashboardCharts'))

const dashboardTraceColumns: Column<EvalTraceSummary>[] = [
  { key: 'status', label: 'Status' },
  { key: 'trace_id', label: 'Trace ID' },
  { key: 'model', label: 'Model', visibleFrom: 'md' },
  { key: 'latency_ms', label: 'Latency', visibleFrom: 'md' },
  { key: 'started_at', label: 'Started' },
  { key: 'action', label: 'Action' },
]

function renderDashboardTraceCell(t: EvalTraceSummary, column: Column<EvalTraceSummary>) {
  switch (column.key) {
    case 'status':
      return (
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-tabular uppercase tracking-[0.15em] ${
            t.status === 'success'
              ? 'bg-[var(--success-soft)] text-[var(--success)]'
              : 'bg-destructive/10 text-destructive'
          }`}
        >
          {t.status}
        </span>
      )
    case 'trace_id':
      return (
        <span className="font-tabular text-xs text-muted-foreground truncate max-w-[120px] inline-block align-middle">
          {t.trace_id}
        </span>
      )
    case 'model':
      return (
        <span className="text-sm text-foreground truncate inline-block max-w-[180px]">
          {t.model?.split('/').pop() ?? '\u2014'}
        </span>
      )
    case 'latency_ms':
      return (
        <span className="font-tabular text-xs text-muted-foreground">
          {t.latency_ms ? `${t.latency_ms}ms` : '\u2014'}
        </span>
      )
    case 'started_at':
      return (
        <span className="font-tabular text-xs text-muted-foreground">
          {formatDateTime(t.started_at)}
        </span>
      )
    case 'action':
      return (
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-1.5">
          {buildConversationHref(t.session_id) ? (
            <Link
              to={buildConversationHref(t.session_id)!}
              className="inline-flex items-center rounded-md border border-border bg-background px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              Conversation
            </Link>
          ) : (
            <span className="text-[11px] text-muted-foreground/60">—</span>
          )}
          {buildTraceHref(t.trace_id) && (
            <Link
              to={buildTraceHref(t.trace_id)!}
              className="inline-flex items-center rounded-md border border-primary/20 bg-primary/5 px-2 py-0.5 text-[11px] font-medium text-primary transition-colors hover:bg-primary/10"
            >
              Trace
            </Link>
          )}
        </div>
      )
    default:
      return null
  }
}

export function Dashboard() {
  const { data: traces = [], isLoading: tLoading, error: tError } = useQuery({
    queryKey: ['eval-traces'],
    queryFn: () => fetchEvalTraces(200),
    refetchInterval: 30_000,
  })

  const { data: costs, isLoading: cLoading, error: cError } = useQuery({
    queryKey: ['session-cost-summary'],
    queryFn: fetchSessionCostSummary,
    refetchInterval: 30_000,
  })

  const { data: categories = [], isLoading: catLoading } = useQuery({
    queryKey: ['question-types'],
    queryFn: () => fetchQuestionTypes(50),
  })

  const { data: guardrails = [] } = useQuery({
    queryKey: ['guardrail-events'],
    queryFn: async () => (await fetchGuardrailEvents({ limit: 100 })).items,
  })

  const loading = tLoading || cLoading || catLoading
  const error = tError || cError

  const [volumeGranularity, setVolumeGranularity] = usePersistedGranularity('request-volume')

  const activityTrend = useMemo(
    () =>
      trailingBuckets(
        traces,
        (t) => t.started_at,
        () => 1,
        volumeGranularity,
      ).map((p) => ({ date: p.label, requests: p.value })),
    [traces, volumeGranularity],
  )

  const successCount = traces.filter((t) => t.status === 'success' || !t.error).length
  const successRate = traces.length
    ? ((successCount / traces.length) * 100).toFixed(1)
    : '0.0'
  const avgLatency = traces.length
    ? Math.round(traces.reduce((s, t) => s + (t.latency_ms ?? 0), 0) / traces.length)
    : 0
  // Backend vocabulary is {block, allow, degraded_allow} — never 'deny'.
  // Use the shared helper so any future rename stays covered in one place.
  const denyCount = guardrails.filter((g) => isBlockingDecision(g.risk_decision ?? '')).length
  const totalCost = costs?.total_cost ?? 0

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="font-tabular text-xs">
          {(error as Error).message}
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6 max-w-[1600px] mx-auto">
      <MobileHeader
        title="Overview"
        description="Real-time metrics from the Mock FinTech Agent Service"
      />

      {/* Signature hero — Total Cost rendered large in JetBrains Mono.
          Instrument-panel read: one dominant number, one inline indicator line,
          flanked by a terse descriptor. This is the "one unforgettable thing"
          for the Dashboard. */}
      <Card
        variant="elevated"
        className="relative overflow-hidden p-6 sm:p-8"
      >
        <div
          aria-hidden
          className="absolute inset-0 opacity-60"
          style={{ backgroundImage: 'var(--atmosphere-radial-1)' }}
        />
        <div className="relative grid gap-6 sm:grid-cols-[1fr_auto] sm:items-end">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="size-1.5 rounded-full bg-[var(--success)] animate-pulse" />
              <span className="text-[10px] font-tabular uppercase tracking-[0.2em] text-muted-foreground">
                live · total cost (usd)
              </span>
            </div>
            {loading ? (
              <Skeleton className="h-16 w-64" />
            ) : (
              <div className="font-tabular text-5xl sm:text-6xl font-light tracking-tight leading-none text-foreground">
                {formatCurrency(totalCost)}
              </div>
            )}
            <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
              <span>
                <span className="font-tabular text-foreground">{traces.length.toLocaleString()}</span>{' '}
                queries
              </span>
              <span className="text-border">/</span>
              <span>
                <span className="font-tabular text-foreground">{costs?.active_sessions?.toLocaleString() ?? '0'}</span>{' '}
                active sessions
              </span>
              <span className="text-border">/</span>
              <span>
                <span className="font-tabular text-foreground">{successRate}%</span> success
              </span>
            </div>
          </div>

          <div className="hidden sm:flex flex-col items-end text-right">
            <span className="text-[10px] font-tabular uppercase tracking-[0.2em] text-muted-foreground mb-2">
              avg latency
            </span>
            <span className="font-tabular text-2xl text-foreground">
              {avgLatency}
              <span className="text-sm text-muted-foreground ml-1">ms</span>
            </span>
            <span className="text-[10px] text-muted-foreground mt-1">
              last {traces.length} runs
            </span>
          </div>
        </div>
      </Card>

      {/* Secondary KPIs — tabular, dense grid */}
      <ResponsiveGrid cols={{ base: 2, lg: 3, xl: 6 }}>
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
          ))
        ) : (
          <>
            <StatCard
              label="Active Sessions"
              value={costs?.active_sessions?.toLocaleString() ?? '0'}
              icon={Users}
              tone="success"
            />
            <StatCard
              label="Total Queries"
              value={traces.length.toLocaleString()}
              icon={MessageSquare}
              tone="info"
            />
            <StatCard
              label="Total Cost"
              value={formatCurrency(totalCost)}
              icon={DollarSign}
              tone="warning"
            />
            <StatCard
              label="Avg Latency"
              value={`${avgLatency}ms`}
              icon={Clock}
              tone="info"
            />
            <StatCard
              label="Success Rate"
              value={`${successRate}%`}
              icon={Activity}
              tone="success"
            />
            <StatCard
              label="Guardrail Blocks"
              value={denyCount.toString()}
              icon={Shield}
              tone={denyCount > 0 ? 'destructive' : 'default'}
            />
          </>
        )}
      </ResponsiveGrid>

      {/* Charts — lazy-loaded chunk */}
      <div className="grid xl:grid-cols-3 gap-6">
        {loading ? (
          <>
            <Skeleton className="xl:col-span-2 h-[360px] rounded-lg" />
            <Skeleton className="h-[360px] rounded-lg" />
          </>
        ) : (
          <Suspense
            fallback={
              <>
                <Skeleton className="xl:col-span-2 h-[360px] rounded-lg" />
                <Skeleton className="h-[360px] rounded-lg" />
              </>
            }
          >
            <DashboardCharts
              activityTrend={activityTrend}
              categories={categories}
              volumeGranularity={volumeGranularity}
              onVolumeGranularityChange={setVolumeGranularity}
            />
          </Suspense>
        )}
      </div>

      {/* Traces table */}
      <Card variant="bordered" className="overflow-hidden">
        <div className="px-6 py-4 border-b border-border flex justify-between items-center">
          <h3 className="text-sm font-medium tracking-tight">Recent Executions</h3>
          <span className="text-[10px] font-tabular uppercase tracking-[0.2em] text-muted-foreground">
            latest 8
          </span>
        </div>
        {loading ? (
          <div className="divide-y divide-border">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="p-4">
                <Skeleton className="h-8 w-full" />
              </div>
            ))}
          </div>
        ) : (
          <ResponsiveTable<EvalTraceSummary>
            columns={dashboardTraceColumns}
            data={traces.slice(0, 8)}
            renderCell={renderDashboardTraceCell}
          />
        )}
      </Card>
    </div>
  )
}
