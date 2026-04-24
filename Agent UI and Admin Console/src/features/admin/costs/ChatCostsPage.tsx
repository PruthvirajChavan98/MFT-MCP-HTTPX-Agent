import { useMemo } from 'react'
import type { ElementType } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  type TooltipContentProps,
} from 'recharts'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'
import {
  Activity,
  Clock,
  DollarSign,
  Hash,
  TrendingUp,
  Users,
} from 'lucide-react'
import { Link } from 'react-router'
import { Alert, AlertDescription } from '@components/ui/alert'
import { ResponsiveGrid } from '@components/ui/responsive-grid'
import { ResponsiveTable, type Column } from '@components/ui/responsive-table'
import { Skeleton } from '@components/ui/skeleton'
import { formatCurrency, formatDateTime } from '@shared/lib/format'
import { mapSessionCostSummary, type CostSessionRow, type CostSeriesPoint } from './viewmodel'
import { sessionCostSummaryQueryOptions } from '@features/admin/query/queryOptions'

type CostTooltipDatum = {
  name: string
  cost: number
}

function isCostTooltipDatum(value: unknown): value is CostTooltipDatum {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return typeof record.name === 'string' && typeof record.cost === 'number'
}

function CostTooltip({ active, payload }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null

  const first = payload[0]
  const datum = isCostTooltipDatum(first.payload) ? first.payload : null
  const numericValue = typeof first.value === 'number' ? first.value : Number(first.value ?? 0)

  return (
    <div className="min-w-[140px] rounded-xl border border-border bg-card p-3 shadow-lg">
      <p className="mb-1 text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">{datum?.name ?? 'Session'}</p>
      <p className="text-[13px] font-tabular font-semibold text-primary">Cost: {formatCurrency(numericValue)}</p>
    </div>
  )
}

function StatCard({
  icon: Icon,
  title,
  value,
  subtitle,
  colors,
}: {
  icon: ElementType
  title: string
  value: string
  subtitle: string
  colors: {
    panel: string
    border: string
    heading: string
    icon: string
    orb: string
  }
}) {
  return (
    <div className={`relative overflow-hidden rounded-2xl border p-5 ${colors.panel} ${colors.border}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={`text-[10px] font-tabular uppercase tracking-[0.15em] ${colors.heading}`}>{title}</p>
          <p className="mt-1 text-3xl font-semibold font-tabular text-foreground leading-none">{value}</p>
          <p className="mt-1.5 text-[11px] text-muted-foreground">{subtitle}</p>
        </div>
        <div className={`rounded-xl p-3 ${colors.icon}`}>
          <Icon className="size-5" />
        </div>
      </div>
      <div className={`absolute -bottom-4 -right-4 size-20 rounded-full ${colors.orb}`} aria-hidden />
    </div>
  )
}

function EmptyCostState() {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-muted/30 px-6 py-10 text-center">
      <p className="text-sm font-semibold text-foreground">No session cost data available yet.</p>
      <p className="mt-1 text-xs text-muted-foreground">Session costs will appear once request usage is tracked.</p>
    </div>
  )
}

function ChartSection({ series }: { series: CostSeriesPoint[] }) {
  if (!series.length) return <EmptyCostState />

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border/60 px-6 pb-2 pt-5">
        <div className="flex items-center gap-2">
          <TrendingUp className="size-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">Cost by Session</span>
        </div>
        <span className="rounded-full border border-primary/20 bg-primary/10 px-2.5 py-1 text-[11px] font-tabular uppercase tracking-[0.15em] text-primary">
          {series.length} session{series.length === 1 ? '' : 's'}
        </span>
      </div>

      <div className="p-6">
        <div className="h-[260px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart accessibilityLayer data={series} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
              <defs>
                <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.22} />
                  <stop offset="95%" stopColor="var(--primary)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
                dy={8}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
                tickFormatter={(value: number) => `$${value.toFixed(4)}`}
                domain={[0, 'auto']}
                width={70}
              />
              <Tooltip content={(props) => <CostTooltip {...props} />} cursor={{ stroke: 'var(--border)', strokeWidth: 1 }} />
              <Area
                type="monotone"
                dataKey="cost"
                stroke="var(--primary)"
                strokeWidth={2.5}
                fill="url(#costGradient)"
                dot={{ r: 5, fill: 'var(--primary)', stroke: 'var(--card)', strokeWidth: 2 }}
                activeDot={{ r: 7, fill: 'var(--primary)', stroke: 'var(--card)', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

const costSessionColumns: Column<CostSessionRow>[] = [
  { key: 'sessionId', label: 'Session ID' },
  { key: 'requests', label: 'Requests' },
  { key: 'cost', label: 'Cost' },
  { key: 'lastActive', label: 'Last Active', visibleFrom: 'md' },
  { key: 'action', label: 'Action' },
]

function renderCostSessionCell(session: CostSessionRow, column: Column<CostSessionRow>) {
  switch (column.key) {
    case 'sessionId':
      return (
        <span className="rounded-lg border border-primary/20 bg-primary/10 px-2.5 py-1 font-tabular text-xs text-primary">
          {session.sessionId}
        </span>
      )
    case 'requests':
      return (
        <span className="inline-flex size-7 items-center justify-center rounded-full bg-[var(--info-soft)] text-[13px] font-tabular font-semibold text-[var(--info)]">
          {session.requests}
        </span>
      )
    case 'cost':
      return (
        <span className="rounded-lg border border-[var(--success)]/30 bg-[var(--success-soft)] px-2.5 py-1 text-[13px] font-tabular font-semibold text-[var(--success)]">
          {formatCurrency(session.cost)}
        </span>
      )
    case 'lastActive':
      return <span className="text-xs font-tabular text-muted-foreground">{formatDateTime(session.lastActive)}</span>
    case 'action':
      return (
        <div className="flex flex-col sm:flex-row gap-1 text-xs">
          {session.conversationHref ? (
            <Link
              to={session.conversationHref}
              className="inline-flex items-center rounded-lg border border-primary/20 bg-primary/5 px-2.5 py-1 font-medium text-primary transition hover:bg-primary/10"
            >
              View Conversation
            </Link>
          ) : (
            <span className="text-muted-foreground">Unavailable</span>
          )}
        </div>
      )
    default:
      return null
  }
}

export function ChatCostsPage() {
  const costsQuery = useQuery(sessionCostSummaryQueryOptions())

  const model = useMemo(() => mapSessionCostSummary(costsQuery.data), [costsQuery.data])

  if (costsQuery.error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{(costsQuery.error as Error).message}</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6 p-1">
      <div className="flex items-center gap-3">
        <div className="rounded-lg bg-primary/10 p-2 ring-1 ring-primary/20">
          <Activity className="size-5 text-primary" />
        </div>
        <div>
          <h1 className="text-xl font-semibold leading-tight text-foreground">Chat Costs</h1>
          <p className="text-xs text-muted-foreground">Monitor session usage and billing</p>
        </div>
      </div>

      <ResponsiveGrid cols={{ base: 1, md: 3 }}>
        {costsQuery.isLoading ? (
          Array.from({ length: 3 }).map((_, idx) => <Skeleton key={idx} className="h-40 rounded-2xl" />)
        ) : (
          <>
            <StatCard
              icon={Users}
              title="Active Sessions"
              value={String(model.activeSessions)}
              subtitle="Currently running"
              colors={{
                panel: 'bg-card',
                border: 'border-border',
                heading: 'text-primary',
                icon: 'bg-primary/10 text-primary ring-1 ring-primary/20',
                orb: 'bg-primary/5',
              }}
            />
            <StatCard
              icon={Hash}
              title="Total Requests"
              value={String(model.totalRequests)}
              subtitle="Across all sessions"
              colors={{
                panel: 'bg-card',
                border: 'border-border',
                heading: 'text-[var(--info)]',
                icon: 'bg-[var(--info-soft)] text-[var(--info)] ring-1 ring-[var(--info)]/20',
                orb: 'bg-[var(--info-soft)]',
              }}
            />
            <StatCard
              icon={DollarSign}
              title="Total Cost"
              value={formatCurrency(model.totalCost)}
              subtitle="Billing period total"
              colors={{
                panel: 'bg-card',
                border: 'border-border',
                heading: 'text-[var(--warning)]',
                icon: 'bg-[var(--warning-soft)] text-[var(--warning)] ring-1 ring-[var(--warning)]/20',
                orb: 'bg-[var(--warning-soft)]',
              }}
            />
          </>
        )}
      </ResponsiveGrid>

      {costsQuery.isLoading ? <Skeleton className="h-[360px] rounded-2xl" /> : <ChartSection series={model.series} />}

      <div className="overflow-hidden rounded-2xl border border-border bg-card">
        <div className="flex items-center gap-2 border-b border-border/60 px-6 py-4">
          <Clock className="size-4 text-muted-foreground" />
          <span className="text-sm font-semibold text-foreground">Session Details</span>
          <span className="ml-auto rounded-full bg-muted px-2.5 py-1 text-[11px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">
            {model.sessions.length} record{model.sessions.length === 1 ? '' : 's'}
          </span>
        </div>

        {costsQuery.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 5 }).map((_, idx) => <Skeleton key={idx} className="h-8" />)}
          </div>
        ) : (
          <ResponsiveTable<CostSessionRow>
            columns={costSessionColumns}
            data={model.sessions}
            renderCell={renderCostSessionCell}
            emptyMessage="No session cost data available."
          />
        )}
      </div>
    </div>
  )
}
