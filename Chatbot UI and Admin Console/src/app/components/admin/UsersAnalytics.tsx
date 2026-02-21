import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { ArrowUpDown, ExternalLink } from 'lucide-react'
import { fetchUserAnalytics } from '../../../shared/api/admin'
import { useAdminContext } from './AdminContext'
import { Card, CardContent } from '../ui/card'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { Progress } from '../ui/progress'
import { formatDateTime } from '../../../shared/lib/format'
import type { UserAnalyticsRow } from '../../../shared/api/admin'

type SortKey = keyof UserAnalyticsRow
export function UsersAnalytics() {
  const auth = useAdminContext()
  const navigate = useNavigate()
  const [sortKey, setSortKey] = useState<SortKey>('trace_count')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const { data = [], isLoading, error } = useQuery({
    queryKey: ['user-analytics', auth.adminKey],
    queryFn: () => fetchUserAnalytics(auth.adminKey),
    enabled: !!auth.adminKey,
  })

  if (!auth.adminKey) return <Alert><AlertDescription>Set X-Admin-Key to view user analytics.</AlertDescription></Alert>
  if (error) return <Alert variant="destructive"><AlertDescription>{(error as Error).message}</AlertDescription></Alert>

  const sorted = [...data].sort((a, b) => {
    const av = a[sortKey] ?? 0; const bv = b[sortKey] ?? 0
    return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
  })

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const Th = ({ label, k }: { label: string; k: SortKey }) => (
    <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide cursor-pointer hover:text-foreground" onClick={() => toggleSort(k)}>
      <div className="flex items-center gap-1">{label}<ArrowUpDown size={10} className={sortKey === k ? 'text-cyan-500' : 'opacity-30'} /></div>
    </th>
  )

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Users & Analytics</h1>
      <Card>
        <CardContent className="p-0">
          {isLoading ? <div className="p-4 space-y-2">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12 rounded" />)}</div> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b">
                  <tr>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Session</th>
                    <Th label="Traces" k="trace_count" />
                    <Th label="Success" k="success_count" />
                    <Th label="Errors" k="error_count" />
                    <Th label="Avg Latency" k="avg_latency_ms" />
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Success Rate</th>
                    <Th label="Last Active" k="last_active" />
                    <th className="px-4 py-2.5 w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((u) => {
                    const total = u.trace_count || 1
                    const rate = Math.round((u.success_count / total) * 100)
                    return (
                      <tr key={u.session_id} className="border-b last:border-0 hover:bg-slate-50/50">
                        <td className="px-4 py-2.5 font-mono text-xs text-slate-500 max-w-[160px] truncate">{u.session_id}</td>
                        <td className="px-4 py-2.5 text-xs font-semibold">{u.trace_count}</td>
                        <td className="px-4 py-2.5 text-xs text-emerald-600">{u.success_count}</td>
                        <td className="px-4 py-2.5 text-xs text-red-500">{u.error_count}</td>
                        <td className="px-4 py-2.5 text-xs">{u.avg_latency_ms ? `${Math.round(u.avg_latency_ms)}ms` : '—'}</td>
                        <td className="px-4 py-2.5 min-w-[120px]">
                          <div className="flex items-center gap-2">
                            <Progress value={rate} className="h-1.5 flex-1" />
                            <span className="text-[10px] text-muted-foreground w-8 text-right">{rate}%</span>
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{formatDateTime(u.last_active)}</td>
                        <td className="px-4 py-2.5 whitespace-nowrap text-right">
                          <button
                            onClick={() => navigate(`/admin/conversations?sessionId=${encodeURIComponent(u.session_id)}`)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-cyan-700 bg-cyan-50/50 hover:bg-cyan-100 hover:text-cyan-800 rounded-md transition-colors border border-cyan-100/50"
                          >
                            <ExternalLink size={12} />
                            View
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                  {!sorted.length && <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-muted-foreground">No data</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
