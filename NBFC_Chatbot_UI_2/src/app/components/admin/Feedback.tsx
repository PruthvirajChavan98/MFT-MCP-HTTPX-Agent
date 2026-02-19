import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ThumbsUp, ThumbsDown, MessageCircle } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { listFeedback, feedbackSummary, createFeedback } from '../../../shared/api/admin'
import { useAdminContext } from './AdminContext'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Textarea } from '../ui/textarea'
import { Label } from '../ui/label'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '../ui/sheet'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import { formatDateTime } from '../../../shared/lib/format'

interface FeedbackForm { session_id: string; trace_id?: string; rating: 'thumbs_up' | 'thumbs_down'; comment?: string; category?: string }

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

export function Feedback() {
  const auth = useAdminContext()
  const qc = useQueryClient()
  const [ratingFilter, setRatingFilter] = useState('all')
  const [sheetOpen, setSheetOpen] = useState(false)
  const form = useForm<FeedbackForm>({ defaultValues: { rating: 'thumbs_up' } })

  const { data: items = [], isLoading: fLoading, error: fError } = useQuery({
    queryKey: ['feedback', auth.adminKey],
    queryFn: () => listFeedback(auth.adminKey),
    enabled: !!auth.adminKey,
  })

  const { data: summary, isLoading: sLoading } = useQuery({
    queryKey: ['feedback-summary', auth.adminKey],
    queryFn: () => feedbackSummary(auth.adminKey),
    enabled: !!auth.adminKey,
  })

  const createMut = useMutation({
    mutationFn: (data: FeedbackForm) => createFeedback(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['feedback'] }); toast.success('Feedback submitted'); setSheetOpen(false); form.reset() },
    onError: (e) => toast.error((e as Error).message),
  })

  if (!auth.adminKey) return <Alert><AlertDescription>Set X-Admin-Key to view feedback.</AlertDescription></Alert>
  if (fError) return <Alert variant="destructive"><AlertDescription>{(fError as Error).message}</AlertDescription></Alert>

  const filtered = ratingFilter === 'all' ? items : items.filter((f) => f.rating === ratingFilter)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold">Feedback</h1>
        <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
          <SheetTrigger asChild><Button size="sm"><MessageCircle size={14} className="mr-1" /> Submit Feedback</Button></SheetTrigger>
          <SheetContent>
            <SheetHeader><SheetTitle className="text-sm">Submit Feedback</SheetTitle></SheetHeader>
            <form onSubmit={form.handleSubmit((d) => createMut.mutate(d))} className="mt-4 space-y-3">
              <div className="space-y-1"><Label className="text-xs">Session ID *</Label><Input {...form.register('session_id', { required: true })} className="text-sm font-mono" /></div>
              <div className="space-y-1"><Label className="text-xs">Trace ID</Label><Input {...form.register('trace_id')} className="text-sm font-mono" /></div>
              <div className="space-y-1">
                <Label className="text-xs">Rating *</Label>
                <Select defaultValue="thumbs_up" onValueChange={(v) => form.setValue('rating', v as 'thumbs_up' | 'thumbs_down')}>
                  <SelectTrigger className="text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="thumbs_up">👍 Thumbs Up</SelectItem><SelectItem value="thumbs_down">👎 Thumbs Down</SelectItem></SelectContent>
                </Select>
              </div>
              <div className="space-y-1"><Label className="text-xs">Category</Label><Input {...form.register('category')} className="text-sm" placeholder="Home Loans, General…" /></div>
              <div className="space-y-1"><Label className="text-xs">Comment</Label><Textarea {...form.register('comment')} rows={3} className="text-sm" /></div>
              <Button type="submit" size="sm" className="w-full" disabled={createMut.isPending}>{createMut.isPending ? 'Submitting…' : 'Submit'}</Button>
            </form>
          </SheetContent>
        </Sheet>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {sLoading ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-lg" />) : (
          <>
            <KpiCard icon={MessageCircle} label="Total Feedback" value={String(summary?.total ?? 0)} color="bg-cyan-500" />
            <KpiCard icon={ThumbsUp} label="Thumbs Up" value={String(summary?.thumbs_up ?? 0)} color="bg-emerald-500" />
            <KpiCard icon={ThumbsDown} label="Thumbs Down" value={String(summary?.thumbs_down ?? 0)} color="bg-red-500" />
          </>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Select value={ratingFilter} onValueChange={setRatingFilter}>
          <SelectTrigger className="w-40 h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All ratings</SelectItem>
            <SelectItem value="thumbs_up">👍 Thumbs Up</SelectItem>
            <SelectItem value="thumbs_down">👎 Thumbs Down</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          {fLoading ? <div className="p-4 space-y-2">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12 rounded" />)}</div> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b">
                  <tr>{['Rating', 'Session', 'Category', 'Comment', 'Time'].map((h) => <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">{h}</th>)}</tr>
                </thead>
                <tbody>
                  {filtered.map((f) => (
                    <tr key={f.id} className="border-b last:border-0 hover:bg-slate-50/50">
                      <td className="px-4 py-2.5">{f.rating === 'thumbs_up' ? <ThumbsUp size={16} className="text-emerald-500" /> : <ThumbsDown size={16} className="text-red-500" />}</td>
                      <td className="px-4 py-2.5 font-mono text-xs text-slate-500 max-w-[130px] truncate">{f.session_id}</td>
                      <td className="px-4 py-2.5 text-xs">{f.category ?? '—'}</td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-[250px] truncate">{f.comment ?? '—'}</td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{formatDateTime(f.created_at)}</td>
                    </tr>
                  ))}
                  {!filtered.length && <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-muted-foreground">No feedback found</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
