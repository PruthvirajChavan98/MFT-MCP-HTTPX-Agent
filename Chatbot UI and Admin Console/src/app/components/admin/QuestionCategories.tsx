import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { fetchQuestionTypes } from '../../../shared/api/admin'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'

export function QuestionCategories() {
  const { data = [], isLoading, error } = useQuery({
    queryKey: ['question-types'],
    queryFn: () => fetchQuestionTypes(100),
  })

  if (error) return <Alert variant="destructive"><AlertDescription>{(error as Error).message}</AlertDescription></Alert>

  const sorted = [...data].sort((a, b) => b.count - a.count)

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Question Categories</h1>

      <Card>
        <CardHeader><CardTitle className="text-sm font-semibold">Category Distribution</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? <Skeleton className="h-64 w-full" /> : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={sorted} layout="vertical" margin={{ left: 120, right: 20, top: 4, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="reason" tick={{ fontSize: 11 }} width={115} />
                <Tooltip formatter={(v: number) => [v, 'Count']} />
                <Bar dataKey="count" fill="#06b6d4" radius={[0, 4, 4, 0]} />
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
                <tr>{['Category', 'Count', 'Share %'].map((h) => <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">{h}</th>)}</tr>
              </thead>
              <tbody>
                {isLoading ? Array.from({ length: 8 }).map((_, i) => (<tr key={i}><td colSpan={3} className="px-4 py-2"><Skeleton className="h-8 rounded" /></td></tr>)) :
                  sorted.map((cat) => (
                    <tr key={cat.reason} className="border-b last:border-0 hover:bg-slate-50/50">
                      <td className="px-4 py-2.5 font-medium">{cat.reason}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{cat.count}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{(cat.pct * 100).toFixed(1)}%</td>
                    </tr>
                  ))
                }
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
