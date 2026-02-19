import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { Activity, CheckCircle, Clock, DollarSign, Hash } from 'lucide-react'
import {
  fetchEvalTraces,
  fetchSessionCostSummary,
  fetchQuestionTypes,
} from '../../../shared/api/admin'
import { useAdminContext } from './AdminContext'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { formatCurrency } from '../../../shared/lib/format'

function KpiCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ElementType
  label: string
  value: string
  sub?: string
  color: string
}) {
  return (
    <Card>
      <CardContent className="p-5 flex items-start gap-4">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={18} className="text-white" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide truncate">
            {label}
          </p>
          <p className="text-2xl font-bold text-foreground mt-0.5">{value}</p>
          {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
        </div>
      </CardContent>
    </Card>
  )
}

export function Dashboard() {
  const {
    data: traces = [],
    isLoading: tLoading,
    error: tError,
  } = useQuery({
    queryKey: ['eval-traces'],
    queryFn: () => fetchEvalTraces(200),
    refetchInterval: 30_000,
  })

  const {
    data: costs,
    isLoading: cLoading,
    error: cError,
  } = useQuery({
    queryKey: ['session-cost-summary'],
    queryFn: fetchSessionCostSummary,
    refetchInterval: 30_000,
  })

  const {
    data: categories = [],
    isLoading: catLoading,
    error: catError,
  } = useQuery({
    queryKey: ['question-types'],
    queryFn: () => fetchQuestionTypes(50),
  })

  const successCount = traces.filter((t) => t.status === 'success' || !t.error).length
  const successRate = traces.length ? Math.round((successCount / traces.length) * 100) : 0
  const avgLatency = traces.length
    ? Math.round(traces.reduce((s, t) => s + (t.latency_ms ?? 0), 0) / traces.length)
    : 0

  const loading = tLoading || cLoading || catLoading
  const err = tError || cError || catError

  if (err) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{(err as Error).message}</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-foreground">Dashboard</h1>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-lg" />)
        ) : (
          <>
            <KpiCard
              icon={Hash}
              label="Total Traces"
              value={traces.length.toLocaleString()}
              color="bg-cyan-500"
            />
            <KpiCard
              icon={CheckCircle}
              label="Success Rate"
              value={`${successRate}%`}
              sub={`${successCount} / ${traces.length}`}
              color="bg-emerald-500"
            />
            <KpiCard
              icon={Clock}
              label="Avg Latency"
              value={`${avgLatency}ms`}
              color="bg-violet-500"
            />
            <KpiCard
              icon={DollarSign}
              label="Total Cost"
              value={formatCurrency(costs?.total_cost ?? 0)}
              sub={`${costs?.total_requests ?? 0} requests`}
              color="bg-amber-500"
            />
          </>
        )}
      </div>

      {/* Question categories chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Question Categories</CardTitle>
        </CardHeader>
        <CardContent>
          {catLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={categories} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="reason" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => [v, 'Count']} />
                <Bar dataKey="count" fill="#06b6d4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Recent traces table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Recent Traces</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {tLoading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 rounded" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b">
                  <tr>
                    {['Trace ID', 'Session', 'Model', 'Latency', 'Status'].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {traces.slice(0, 20).map((t) => (
                    <tr key={t.trace_id} className="border-b last:border-0 hover:bg-slate-50/50">
                      <td className="px-4 py-2 font-mono text-xs text-slate-500 max-w-[140px] truncate">
                        {t.trace_id}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-slate-500 max-w-[100px] truncate">
                        {t.session_id}
                      </td>
                      <td className="px-4 py-2 text-xs">{t.model ?? '—'}</td>
                      <td className="px-4 py-2 text-xs">{t.latency_ms ? `${t.latency_ms}ms` : '—'}</td>
                      <td className="px-4 py-2">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${
                            t.error
                              ? 'bg-red-100 text-red-700'
                              : 'bg-emerald-100 text-emerald-700'
                          }`}
                        >
                          {t.error ? 'error' : 'ok'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
