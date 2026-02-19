import { useState, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, Upload, Search } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { fetchFaqs, updateFaq, deleteFaq, ingestFaqBatch } from '../../../shared/api/admin'
import { useAdminContext } from './AdminContext'
import type { FaqRecord } from '../../../shared/types/admin'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Textarea } from '../ui/textarea'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../ui/alert-dialog'
import { Badge } from '../ui/badge'
import { Progress } from '../ui/progress'

interface FaqForm {
  question: string
  answer: string
}

export function KnowledgeBase() {
  const auth = useAdminContext()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState<FaqRecord | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [ingestProgress, setIngestProgress] = useState<string | null>(null)
  const [batchText, setBatchText] = useState('')

  const { data: faqs = [], isLoading, error } = useQuery({
    queryKey: ['faqs', auth.adminKey],
    queryFn: () => fetchFaqs(auth.adminKey),
    enabled: !!auth.adminKey,
  })

  const form = useForm<FaqForm>({ defaultValues: { question: '', answer: '' } })

  const filtered = faqs.filter(
    (f) =>
      !search ||
      f.question.toLowerCase().includes(search.toLowerCase()) ||
      f.answer.toLowerCase().includes(search.toLowerCase()),
  )

  const saveMut = useMutation({
    mutationFn: (data: FaqForm) =>
      editing
        ? updateFaq(auth.adminKey, { original_question: editing.question, new_question: data.question, new_answer: data.answer })
        : updateFaq(auth.adminKey, { original_question: data.question, new_question: data.question, new_answer: data.answer }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['faqs'] })
      toast.success(editing ? 'FAQ updated' : 'FAQ added')
      setDialogOpen(false)
      setEditing(null)
      form.reset()
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const deleteMut = useMutation({
    mutationFn: (question: string) => deleteFaq(auth.adminKey, question),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['faqs'] })
      toast.success('FAQ deleted')
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const handleEdit = (faq: FaqRecord) => {
    setEditing(faq)
    form.reset({ question: faq.question, answer: faq.answer })
    setDialogOpen(true)
  }

  const handleAdd = () => {
    setEditing(null)
    form.reset({ question: '', answer: '' })
    setDialogOpen(true)
  }

  const handleBatchIngest = useCallback(async () => {
    if (!batchText.trim() || !auth.adminKey) return
    const lines = batchText.trim().split('\n').filter(Boolean)
    const items = lines.map((line) => {
      const [question, ...rest] = line.split('|')
      return { question: question.trim(), answer: rest.join('|').trim() }
    }).filter((item) => item.question && item.answer)
    if (!items.length) { toast.error('Format: question|answer per line'); return }
    setIngestProgress('Starting...')
    try {
      await ingestFaqBatch(auth.adminKey, items, (msg) => setIngestProgress(msg), auth.openrouterKey, auth.groqKey)
      toast.success('Batch ingest complete')
      qc.invalidateQueries({ queryKey: ['faqs'] })
      setBatchText('')
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setIngestProgress(null)
    }
  }, [auth.adminKey, auth.openrouterKey, auth.groqKey, batchText, qc])

  if (!auth.adminKey) return <Alert><AlertDescription>Set X-Admin-Key in the header to use Knowledge Base.</AlertDescription></Alert>
  if (error) return <Alert variant="destructive"><AlertDescription>{(error as Error).message}</AlertDescription></Alert>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h1 className="text-xl font-semibold">Knowledge Base</h1>
        <Button size="sm" onClick={handleAdd}><Plus size={14} className="mr-1" /> Add FAQ</Button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input placeholder="Search FAQs…" className="pl-8 h-8 text-sm" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {/* Batch ingest */}
      <Card>
        <CardHeader><CardTitle className="text-sm">Batch Ingest (question|answer per line)</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <Textarea value={batchText} onChange={(e) => setBatchText(e.target.value)} placeholder="What is your rate?|Our rate starts at 8.5% p.a." rows={4} className="text-sm font-mono" />
          {ingestProgress && <div className="space-y-1"><p className="text-xs text-muted-foreground">{ingestProgress}</p><Progress value={50} className="h-1.5" /></div>}
          <Button size="sm" variant="outline" onClick={handleBatchIngest} disabled={!batchText.trim() || !!ingestProgress}><Upload size={13} className="mr-1" /> Ingest</Button>
        </CardContent>
      </Card>

      {/* FAQs table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-4 space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 rounded" />)}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b">
                  <tr>
                    {['Question', 'Answer', 'Actions'].map((h) => (
                      <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((faq) => (
                    <tr key={faq.question} className="border-b last:border-0 hover:bg-slate-50/50">
                      <td className="px-4 py-3 max-w-[280px]"><p className="font-medium text-sm line-clamp-2">{faq.question}</p></td>
                      <td className="px-4 py-3 max-w-[380px]"><p className="text-sm text-muted-foreground line-clamp-2">{faq.answer}</p></td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => handleEdit(faq)}><Pencil size={13} /></Button>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button size="icon" variant="ghost" className="h-7 w-7 text-destructive hover:text-destructive"><Trash2 size={13} /></Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Delete FAQ?</AlertDialogTitle>
                                <AlertDialogDescription>This action cannot be undone.</AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction onClick={() => deleteMut.mutate(faq.question)}>Delete</AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!filtered.length && <tr><td colSpan={3} className="px-4 py-8 text-center text-sm text-muted-foreground">No FAQs found</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add/Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>{editing ? 'Edit FAQ' : 'Add FAQ'}</DialogTitle></DialogHeader>
          <form onSubmit={form.handleSubmit((d) => saveMut.mutate(d))} className="space-y-3">
            <div>
              <label className="text-xs font-medium">Question</label>
              <Input {...form.register('question', { required: true })} className="mt-1 text-sm" />
            </div>
            <div>
              <label className="text-xs font-medium">Answer</label>
              <Textarea {...form.register('answer', { required: true })} rows={4} className="mt-1 text-sm" />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" size="sm" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button type="submit" size="sm" disabled={saveMut.isPending}>{saveMut.isPending ? 'Saving…' : 'Save'}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
