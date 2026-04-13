import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { ExternalLink } from 'lucide-react'
import { fetchUserAnalytics } from '@features/admin/api/admin'
import { Card, CardContent } from '@components/ui/card'
import { Skeleton } from '@components/ui/skeleton'
import { Alert, AlertDescription } from '@components/ui/alert'
import { Progress } from '@components/ui/progress'
import { ResponsiveTable, type Column } from '@components/ui/responsive-table'
import { formatDateTime } from '@shared/lib/format'
import type { UserAnalyticsRow } from '@features/admin/api/admin'

type SortKey = keyof UserAnalyticsRow

const userColumns: Column<UserAnalyticsRow>[] = [
  { key: 'session_id', label: 'Session' },
  { key: 'trace_count', label: 'Traces' },
  { key: 'success_count', label: 'Success' },
  { key: 'error_count', label: 'Errors' },
  { key: 'avg_latency_ms', label: 'Avg Latency', visibleFrom: 'md' },
  { key: 'success_rate', label: 'Success Rate' },
  { key: 'last_active', label: 'Last Active', visibleFrom: 'md' },
  { key: 'action', label: '' },
]

export function UsersAnalytics() {
  const navigate = useNavigate()
  const [sortKey, setSortKey] = useState<SortKey>('trace_count')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const { data = [], isLoading, error } = useQuery({
    queryKey: ['user-analytics'],
    queryFn: () => fetchUserAnalytics(),
  })
  if (error) return <Alert variant="destructive"><AlertDescription>{(error as Error).message}</AlertDescription></Alert>

  const sorted = [...data].sort((a, b) => {
    const av = a[sortKey] ?? 0; const bv = b[sortKey] ?? 0
    return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
  })

  const renderUserCell = (u: UserAnalyticsRow, column: Column<UserAnalyticsRow>) => {
    const total = u.trace_count || 1
    const rate = Math.round((u.success_count / total) * 100)

    switch (column.key) {
      case 'session_id':
        return <span className="font-mono text-xs text-slate-500 max-w-40 truncate">{u.session_id}</span>
      case 'trace_count':
        return <span className="text-xs font-semibold">{u.trace_count}</span>
      case 'success_count':
        return <span className="text-xs text-emerald-600">{u.success_count}</span>
      case 'error_count':
        return <span className="text-xs text-red-500">{u.error_count}</span>
      case 'avg_latency_ms':
        return <span className="text-xs">{u.avg_latency_ms ? `${Math.round(u.avg_latency_ms)}ms` : '\u2014'}</span>
      case 'success_rate':
        return (
          <div className="min-w-30">
            <div className="hidden md:flex items-center gap-2">
              <Progress value={rate} className="h-1.5 flex-1" />
              <span className="text-[10px] text-muted-foreground w-8 text-right">{rate}%</span>
            </div>
            <span className="md:hidden text-xs text-muted-foreground">{rate}%</span>
          </div>
        )
      case 'last_active':
        return <span className="text-xs text-muted-foreground whitespace-nowrap">{formatDateTime(u.last_active)}</span>
      case 'action':
        return (
          <div className="whitespace-nowrap text-right">
            <button
              onClick={() => navigate(`/admin/conversations?sessionId=${encodeURIComponent(u.session_id)}`)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-cyan-700 bg-cyan-50/50 hover:bg-cyan-100 hover:text-cyan-800 rounded-md transition-colors border border-cyan-100/50"
            >
              <ExternalLink size={12} />
              View
            </button>
          </div>
        )
      default:
        return null
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Users & Analytics</h1>
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-4 space-y-2">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12 rounded" />)}</div>
          ) : (
            <ResponsiveTable<UserAnalyticsRow>
              columns={userColumns}
              data={sorted}
              renderCell={renderUserCell}
              emptyMessage="No data"
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
