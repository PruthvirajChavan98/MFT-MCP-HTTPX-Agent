import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { DollarSign, Hash, Users } from 'lucide-react'
import { fetchSessionCostSummary } from '../../../shared/api/admin'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { formatCurrency } from '../../../shared/lib/format'
import { formatDateTime } from '../../../shared/lib/format'

function KpiCard({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: string; color: string }) {
  return (
    <Card>
      <CardContent className="p-5 flex items-start gap-4">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}><Icon size={18} className="text-white" /></div>
        <div><p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{label}</p><p className="text-2xl font-bold mt-0.5">{value}</p></div>
      </CardContent>
    </Card>
  )
}

export function ChatCosts() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['session-cost-summary'],
    queryFn: fetchSessionCostSummary,
    refetchInterval: 30_000,
  })

  if (error) return <Alert variant="destructive"><AlertDescription>{(error as Error).message}</AlertDescription></Alert>

  const chartData = (data?.sessions ?? []).map((s, i) => ({ name: `S${i + 1}`, cost: s.total_cost, requests: s.total_requests }))

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Chat Costs</h1>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {isLoading ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-lg" />) : (
          <>
            <KpiCard icon={Users} label="Active Sessions" value={String(data?.active_sessions ?? 0)} color="bg-cyan-500" />
            <KpiCard icon={Hash} label="Total Requests" value={String(data?.total_requests ?? 0)} color="bg-violet-500" />
            <KpiCard icon={DollarSign} label="Total Cost" value={formatCurrency(data?.total_cost ?? 0)} color="bg-amber-500" />
          </>
        )}
      </div>

      <Card>
        <CardHeader><CardTitle className="text-sm font-semibold">Cost by Session</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? <Skeleton className="h-64 w-full" /> : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${v.toFixed(4)}`} />
                <Tooltip formatter={(v: number) => [formatCurrency(v), 'Cost']} />
                <Line type="monotone" dataKey="cost" stroke="#06b6d4" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b">
                <tr>{['Session ID', 'Requests', 'Cost', 'Last Active'].map((h) => <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">{h}</th>)}</tr>
              </thead>
              <tbody>
                {(data?.sessions ?? []).sort((a, b) => b.total_cost - a.total_cost).map((s) => (
                  <tr key={s.session_id} className="border-b last:border-0 hover:bg-slate-50/50">
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-500 max-w-[160px] truncate">{s.session_id}</td>
                    <td className="px-4 py-2.5 text-xs">{s.total_requests}</td>
                    <td className="px-4 py-2.5 text-xs font-semibold">{formatCurrency(s.total_cost)}</td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground">{formatDateTime(s.last_request_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
