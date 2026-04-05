import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { fetchQuestionTypes } from '@features/admin/api/admin'
import { useAdminContext } from '@features/admin/context/AdminContext'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Skeleton } from '@components/ui/skeleton'
import { Alert, AlertDescription } from '@components/ui/alert'
import { MobileHeader } from '@components/ui/mobile-header'
import { ResponsiveGrid } from '@components/ui/responsive-grid'

function humanizeCategory(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

export function QuestionCategories() {
  const auth = useAdminContext()

  const { data = [], isLoading, error } = useQuery({
    queryKey: ['question-types', auth.adminKey],
    queryFn: () => fetchQuestionTypes(auth.adminKey, 200),
    refetchInterval: 30_000,
  })

  const sorted = useMemo(() => [...data].sort((a, b) => b.count - a.count), [data])
  const totalClassified = useMemo(() => sorted.reduce((sum, item) => sum + item.count, 0), [sorted])

  const topCategory = sorted[0]
  const unknownShare = sorted.find((item) => item.reason.toLowerCase() === 'unknown')?.pct ?? 0
  const coverage = 1 - unknownShare

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{(error as Error).message}</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <MobileHeader
        title="Question Categories"
        description="Distribution of routed business categories for recent traces."
      />

      <ResponsiveGrid cols={{ base: 2, xl: 4 }} gap={4}>
        {isLoading ? (
          Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-24 rounded-lg" />)
        ) : (
          <>
            <Card><CardContent className="p-5"><p className="text-xs uppercase tracking-wide text-muted-foreground">Top Category</p><p className="text-base font-semibold mt-1">{topCategory ? humanizeCategory(topCategory.reason) : '—'}</p></CardContent></Card>
            <Card><CardContent className="p-5"><p className="text-xs uppercase tracking-wide text-muted-foreground">Unknown Share</p><p className="text-2xl font-bold mt-1">{(unknownShare * 100).toFixed(1)}%</p></CardContent></Card>
            <Card><CardContent className="p-5"><p className="text-xs uppercase tracking-wide text-muted-foreground">Coverage</p><p className="text-2xl font-bold mt-1">{(coverage * 100).toFixed(1)}%</p></CardContent></Card>
            <Card><CardContent className="p-5"><p className="text-xs uppercase tracking-wide text-muted-foreground">Total Classified</p><p className="text-2xl font-bold mt-1">{totalClassified}</p></CardContent></Card>
          </>
        )}
      </ResponsiveGrid>

      <Card>
        <CardHeader><CardTitle className="text-sm font-semibold">Category Distribution</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-72 w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={sorted.slice(0, 12)} layout="vertical" margin={{ left: 10, right: 20, top: 6, bottom: 6 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="reason" tickFormatter={humanizeCategory} tick={{ fontSize: 11 }} width={120} />
                <Tooltip formatter={(value: number, _name, payload) => [value, humanizeCategory(String(payload?.payload?.reason || ''))]} />
                <Bar dataKey="count" fill="#06b6d4" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b">
                <tr>
                  {['Category', 'Count', 'Share %', 'Coverage Bar', 'Action'].map((heading) => (
                    <th key={heading} className={`px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide${heading === 'Coverage Bar' ? ' hidden md:table-cell' : ''}`}>{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading
                  ? Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i}><td colSpan={5} className="px-4 py-2"><Skeleton className="h-8 rounded" /></td></tr>
                    ))
                  : sorted.map((category) => (
                      <tr key={category.reason} className="border-b last:border-0 hover:bg-slate-50/50">
                        <td className="px-4 py-2.5 font-medium">{humanizeCategory(category.reason)}</td>
                        <td className="px-4 py-2.5 text-muted-foreground">{category.count}</td>
                        <td className="px-4 py-2.5 text-muted-foreground">{(category.pct * 100).toFixed(1)}%</td>
                        <td className="hidden md:table-cell px-4 py-2.5 min-w-[220px]">
                          <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                            <div className="h-full bg-cyan-500" style={{ width: `${Math.max(2, category.pct * 100)}%` }} />
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-xs">
                          <Link
                            to={`/admin/traces?search=${encodeURIComponent(category.reason)}`}
                            className="inline-flex items-center rounded-md border border-cyan-200 bg-cyan-50 px-2.5 py-1 font-semibold text-cyan-700 transition hover:bg-cyan-100"
                          >
                            View Traces
                          </Link>
                        </td>
                      </tr>
                    ))}
                {!isLoading && !sorted.length && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-muted-foreground">
                      No category data available.
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
