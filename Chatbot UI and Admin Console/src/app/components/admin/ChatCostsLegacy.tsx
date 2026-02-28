import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { DollarSign, Hash, Users, TrendingUp, MessageSquare } from 'lucide-react'
import { Link } from 'react-router'
import { fetchSessionCostSummary } from '../../../shared/api/admin'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { formatCurrency, formatDateTime } from '../../../shared/lib/format'
import { buildConversationHref } from '../../../shared/lib/admin-links'

type SortKey = 'total_cost' | 'total_requests' | 'last_request_at'

function KpiCard({ icon: Icon, label, value, note, color }: { icon: React.ElementType; label: string; value: string; note?: string; color: string }) {
  return (
    <Card>
      <CardContent className="p-5 flex items-start gap-4">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={18} className="text-white" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{label}</p>
          <p className="text-2xl font-bold mt-0.5">{value}</p>
          {note ? <p className="text-[11px] text-muted-foreground mt-1">{note}</p> : null}
        </div>
      </CardContent>
    </Card>
  )
}

export function ChatCostsLegacy() {
  const [sortKey, setSortKey] = useState<SortKey>('total_cost')

  const { data, isLoading, error } = useQuery({
    queryKey: ['session-cost-summary'],
    queryFn: fetchSessionCostSummary,
    refetchInterval: 30_000,
  })

  if (error)
    return (
      <Alert variant="destructive">
        <AlertDescription>{(error as Error).message}</AlertDescription>
      </Alert>
    )

  const sessions = useMemo(() => {
    const rows = [...(data?.sessions ?? [])]
    rows.sort((a, b) => {
      if (sortKey === 'last_request_at') {
        const av = a.last_request_at || ''
        const bv = b.last_request_at || ''
        return av < bv ? 1 : -1
      }
      return (b[sortKey] as number) - (a[sortKey] as number)
    })
    return rows
  }, [data?.sessions, sortKey])

  const averageCostPerRequest = data?.total_requests
    ? (data.total_cost ?? 0) / data.total_requests
    : 0

  const topSessionShare = sessions.length && (data?.total_cost ?? 0) > 0
    ? ((sessions[0]?.total_cost ?? 0) / (data?.total_cost ?? 1)) * 100
    : 0

  const chartData = sessions.slice(0, 12).map((session) => ({
    session_id: session.session_id,
    label: `${session.session_id.slice(0, 10)}…`,
    cost: session.total_cost,
    requests: session.total_requests,
  }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Session Costs</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Cost metrics are computed from streamed usage events and aggregated per session.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
        {isLoading ? (
          Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-lg" />)
        ) : (
          <>
            <KpiCard icon={Users} label="Active Sessions" value={String(data?.active_sessions ?? 0)} color="bg-cyan-500" />
            <KpiCard icon={Hash} label="Total Requests" value={String(data?.total_requests ?? 0)} color="bg-violet-500" />
            <KpiCard icon={DollarSign} label="Total Cost" value={formatCurrency(data?.total_cost ?? 0)} color="bg-amber-500" />
            <KpiCard icon={TrendingUp} label="Avg Cost / Request" value={formatCurrency(averageCostPerRequest)} color="bg-emerald-500" />
            <KpiCard icon={MessageSquare} label="Top Session Share" value={`${topSessionShare.toFixed(1)}%`} note="of total spend" color="bg-indigo-500" />
          </>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Cost by Session</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-72 w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} margin={{ left: 12, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11 }}
                  interval={0}
                  angle={-20}
                  textAnchor="end"
                  height={60}
                />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(value) => `$${Number(value).toFixed(5)}`} />
                <Tooltip
                  formatter={(value: number, name) => [name === 'cost' ? formatCurrency(value) : value, name === 'cost' ? 'Cost' : 'Requests']}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.session_id || ''}
                />
                <Bar dataKey="cost" fill="#06b6d4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="p-3 border-b bg-slate-50 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-muted-foreground font-medium">Sort by:</span>
            {[
              ['total_cost', 'Cost'],
              ['total_requests', 'Requests'],
              ['last_request_at', 'Last Active'],
            ].map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setSortKey(key as SortKey)}
                className={`px-2.5 py-1 rounded border ${sortKey === key ? 'bg-cyan-50 border-cyan-200 text-cyan-700' : 'bg-white'}`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b">
                <tr>
                  {['Session ID', 'Requests', 'Cost', 'Last Active', 'Action'].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr key={session.session_id} className="border-b last:border-0 hover:bg-slate-50/50">
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-500 max-w-[240px] truncate">{session.session_id}</td>
                    <td className="px-4 py-2.5 text-xs">{session.total_requests}</td>
                    <td className="px-4 py-2.5 text-xs font-semibold">{formatCurrency(session.total_cost)}</td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground">{formatDateTime(session.last_request_at)}</td>
                    <td className="px-4 py-2.5 text-xs">
                      {buildConversationHref(session.session_id) ? (
                        <Link
                          to={buildConversationHref(session.session_id)!}
                          className="inline-flex items-center rounded-md border border-cyan-200 bg-cyan-50 px-2.5 py-1 font-semibold text-cyan-700 transition hover:bg-cyan-100"
                        >
                          View Conversation
                        </Link>
                      ) : (
                        <span className="text-muted-foreground">Unavailable</span>
                      )}
                    </td>
                  </tr>
                ))}
                {!sessions.length && !isLoading && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-muted-foreground">
                      No session cost data available.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
