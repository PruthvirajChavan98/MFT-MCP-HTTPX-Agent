import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ThumbsUp, ThumbsDown, MessageCircle } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { listFeedback, feedbackSummary, createFeedback } from '@features/admin/api/admin'
import { Card, CardContent } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Input } from '@components/ui/input'
import { MobileHeader } from '@components/ui/mobile-header'
import { ResponsiveGrid } from '@components/ui/responsive-grid'
import { ResponsiveTable, type Column } from '@components/ui/responsive-table'
import { Textarea } from '@components/ui/textarea'
import { Label } from '@components/ui/label'
import { Skeleton } from '@components/ui/skeleton'
import { Alert, AlertDescription } from '@components/ui/alert'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@components/ui/sheet'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@components/ui/select'
import { formatDateTime } from '@shared/lib/format'
import type { FeedbackRecord } from '@features/admin/types/admin'

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

const feedbackColumns: Column<FeedbackRecord>[] = [
  { key: 'rating', label: 'Rating' },
  { key: 'session_id', label: 'Session' },
  { key: 'category', label: 'Category' },
  { key: 'comment', label: 'Comment', visibleFrom: 'md', className: 'max-w-[250px]' },
  { key: 'created_at', label: 'Time' },
]

function renderFeedbackCell(f: FeedbackRecord, column: Column<FeedbackRecord>) {
  switch (column.key) {
    case 'rating':
      return f.rating === 'thumbs_up'
        ? <ThumbsUp size={16} className="text-emerald-500" />
        : <ThumbsDown size={16} className="text-red-500" />
    case 'session_id':
      return <span className="font-mono text-xs text-slate-500 max-w-[130px] truncate">{f.session_id}</span>
    case 'category':
      return <span className="text-xs">{f.category ?? '\u2014'}</span>
    case 'comment':
      return <span className="text-xs text-muted-foreground truncate">{f.comment ?? '\u2014'}</span>
    case 'created_at':
      return <span className="text-xs text-muted-foreground whitespace-nowrap">{formatDateTime(f.created_at)}</span>
    default:
      return null
  }
}

export function Feedback() {
  const qc = useQueryClient()
  const [ratingFilter, setRatingFilter] = useState('all')
  const [sheetOpen, setSheetOpen] = useState(false)
  const form = useForm<FeedbackForm>({ defaultValues: { rating: 'thumbs_up' } })

  const { data: items = [], isLoading: fLoading, error: fError } = useQuery({
    queryKey: ['feedback'],
    queryFn: () => listFeedback(),
  })

  const { data: summary, isLoading: sLoading } = useQuery({
    queryKey: ['feedback-summary'],
    queryFn: () => feedbackSummary(),
  })

  const createMut = useMutation({
    mutationFn: (data: FeedbackForm) => createFeedback(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['feedback'] }); toast.success('Feedback submitted'); setSheetOpen(false); form.reset() },
    onError: (e) => toast.error((e as Error).message),
  })

  if (fError) return <Alert variant="destructive"><AlertDescription>{(fError as Error).message}</AlertDescription></Alert>

  const filtered = ratingFilter === 'all' ? items : items.filter((f) => f.rating === ratingFilter)

  return (
    <div className="space-y-6">
      <MobileHeader
        title="Feedback"
        actions={
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
                    <SelectContent><SelectItem value="thumbs_up">Thumbs Up</SelectItem><SelectItem value="thumbs_down">Thumbs Down</SelectItem></SelectContent>
                  </Select>
                </div>
                <div className="space-y-1"><Label className="text-xs">Category</Label><Input {...form.register('category')} className="text-sm" placeholder="Home Loans, General..." /></div>
                <div className="space-y-1"><Label className="text-xs">Comment</Label><Textarea {...form.register('comment')} rows={3} className="text-sm" /></div>
                <Button type="submit" size="sm" className="w-full" disabled={createMut.isPending}>{createMut.isPending ? 'Submitting...' : 'Submit'}</Button>
              </form>
            </SheetContent>
          </Sheet>
        }
      />

      <ResponsiveGrid cols={{ base: 1, sm: 3 }}>
        {sLoading ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-lg" />) : (
          <>
            <KpiCard icon={MessageCircle} label="Total Feedback" value={String(summary?.total ?? 0)} color="bg-cyan-500" />
            <KpiCard icon={ThumbsUp} label="Thumbs Up" value={String(summary?.thumbs_up ?? 0)} color="bg-emerald-500" />
            <KpiCard icon={ThumbsDown} label="Thumbs Down" value={String(summary?.thumbs_down ?? 0)} color="bg-red-500" />
          </>
        )}
      </ResponsiveGrid>

      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
        <Select value={ratingFilter} onValueChange={setRatingFilter}>
          <SelectTrigger className="w-full sm:w-40 h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All ratings</SelectItem>
            <SelectItem value="thumbs_up">Thumbs Up</SelectItem>
            <SelectItem value="thumbs_down">Thumbs Down</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          {fLoading ? (
            <div className="p-4 space-y-2">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12 rounded" />)}</div>
          ) : (
            <ResponsiveTable<FeedbackRecord>
              columns={feedbackColumns}
              data={filtered}
              renderCell={renderFeedbackCell}
              emptyMessage="No feedback found"
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
