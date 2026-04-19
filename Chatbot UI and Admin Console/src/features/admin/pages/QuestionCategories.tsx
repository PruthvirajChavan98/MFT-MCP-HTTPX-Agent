import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { fetchQuestionTypes } from '@features/admin/api/admin'
import { formatCategoryLabel, isOtherCategory } from '@features/admin/lib/categoryLabels'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Skeleton } from '@components/ui/skeleton'
import { Alert, AlertDescription } from '@components/ui/alert'
import { MobileHeader } from '@components/ui/mobile-header'
import { ResponsiveGrid } from '@components/ui/responsive-grid'

export function QuestionCategories() {
  const { data = [], isLoading, error } = useQuery({
    queryKey: ['question-types'],
    queryFn: () => fetchQuestionTypes(200),
    refetchInterval: 30_000,
  })

  const sorted = useMemo(() => [...data].sort((a, b) => b.count - a.count), [data])
  const totalClassified = useMemo(() => sorted.reduce((sum, item) => sum + item.count, 0), [sorted])

  const topCategory = sorted[0]
  const unknownShare = sorted.find((item) => isOtherCategory(item.reason))?.pct ?? 0
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
            <Card><CardContent className="p-5"><p className="text-xs uppercase tracking-wide text-muted-foreground">Top Category</p><p className="text-base font-semibold mt-1">{topCategory ? formatCategoryLabel(topCategory.reason) : '—'}</p></CardContent></Card>
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
                <CartesianGrid strokeDasharray="2 4" stroke="var(--border)" horizontal={false} />
                <XAxis type="number" tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
                <YAxis type="category" dataKey="reason" tickFormatter={formatCategoryLabel} tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }} axisLine={false} tickLine={false} width={180} />
                <Tooltip
                  cursor={{ fill: 'var(--accent)' }}
                  contentStyle={{
                    borderRadius: 6,
                    border: '1px solid var(--border)',
                    backgroundColor: 'var(--card)',
                    color: 'var(--foreground)',
                    fontSize: 12,
                  }}
                  formatter={(value: number, _name, payload) => [value, formatCategoryLabel(String(payload?.payload?.reason || ''))]}
                />
                <Bar dataKey="count" fill="var(--primary)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 border-b border-border">
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
                      <tr key={category.reason} className="border-b border-border last:border-0 hover:bg-accent/40 transition-colors">
                        <td className="px-4 py-2.5 font-medium text-foreground">{formatCategoryLabel(category.reason)}</td>
                        <td className="px-4 py-2.5 font-tabular text-muted-foreground">{category.count}</td>
                        <td className="px-4 py-2.5 font-tabular text-muted-foreground">{(category.pct * 100).toFixed(1)}%</td>
                        <td className="hidden md:table-cell px-4 py-2.5 min-w-[220px]">
                          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                            <div className="h-full bg-primary" style={{ width: `${Math.max(2, category.pct * 100)}%` }} />
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-xs">
                          <Link
                            to={`/admin/traces?category=${encodeURIComponent(category.reason)}`}
                            className="inline-flex items-center rounded-md border border-primary/20 bg-primary/10 px-2.5 py-1 font-medium text-primary transition-colors hover:bg-primary/20"
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
