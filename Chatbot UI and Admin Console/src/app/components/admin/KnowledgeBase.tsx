import { useState, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, Upload, Search, Database, Sparkles, AlertTriangle, Loader2 } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { fetchFaqs, updateFaq, deleteFaq, ingestFaqBatch, requestJson } from '../../../shared/api/admin'
import { useAdminContext } from './AdminContext'
import type { FaqRecord } from '../../../shared/types/admin'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '../ui/alert-dialog'
import { Progress } from '../ui/progress'

export function KnowledgeBase() {
  const auth = useAdminContext();
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<FaqRecord | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [batchText, setBatchText] = useState('');
  const [ingestProgress, setIngestProgress] = useState<string | null>(null);

  const [semanticMode, setSemanticMode] = useState(false);
  const [semanticResults, setSemanticResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const { data: faqs = [], isLoading } = useQuery({
    queryKey: ['faqs', auth.adminKey],
    queryFn: () => fetchFaqs(auth.adminKey),
    enabled: !!auth.adminKey,
  });

  const { register, handleSubmit, reset } = useForm({ defaultValues: { question: '', answer: '' } });

  const filtered = faqs.filter((f) => !search || f.question.toLowerCase().includes(search.toLowerCase()) || f.answer.toLowerCase().includes(search.toLowerCase()));

  const saveMut = useMutation({
    mutationFn: (data: any) => updateFaq(auth.adminKey, { original_question: editing ? editing.question : data.question, new_question: data.question, new_answer: data.answer }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['faqs'] }); toast.success('Saved successfully'); setDialogOpen(false); reset(); },
    onError: (e) => toast.error((e as Error).message),
  });

  const deleteMut = useMutation({
    mutationFn: (q: string) => deleteFaq(auth.adminKey, q),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['faqs'] }); toast.success('Deleted successfully'); },
  });

  const handleSemanticSearch = async () => {
    if (!search.trim() || !auth.openrouterKey) return toast.error("OpenRouter key required for semantic search");
    setIsSearching(true);
    try {
      const res: any = await requestJson({
        method: 'POST', path: '/agent/admin/faqs/semantic-search',
        body: { query: search, limit: 5 },
        headers: { 'X-Admin-Key': auth.adminKey, 'X-OpenRouter-Key': auth.openrouterKey }
      });
      setSemanticResults(res.results || []);
    } catch (e) { toast.error(String(e)); } finally { setIsSearching(false); }
  };

  const handleBatchIngest = useCallback(async () => {
    if (!batchText.trim()) return;
    const items = batchText.trim().split('\n').filter(Boolean).map(line => {
      const [q, ...rest] = line.split('|');
      return { question: q.trim(), answer: rest.join('|').trim() };
    }).filter(i => i.question && i.answer);

    if (!items.length) return toast.error('Use format: question|answer');

    setIngestProgress('Starting ingestion pipeline...');
    try {
      await ingestFaqBatch(auth.adminKey, items, (msg) => setIngestProgress(msg), auth.openrouterKey, auth.groqKey);
      toast.success('Batch ingest complete');
      qc.invalidateQueries({ queryKey: ['faqs'] });
      setBatchText('');
    } catch (e) { toast.error((e as Error).message); } finally { setIngestProgress(null); }
  }, [auth, batchText, qc]);

  if (!auth.adminKey) return <div className="p-8 text-center bg-red-50 text-red-600 rounded-xl font-medium mt-10 max-w-2xl mx-auto border border-red-200">Admin API Key Required. Configure in Header.</div>;

  return (
    <div className="space-y-8 max-w-[1600px] mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl text-gray-900 tracking-tight" style={{ fontWeight: 700 }}>Knowledge Base</h1>
          <p className="text-gray-500 text-sm mt-1">Manage FAQs, vector embeddings, and Neo4j graph relationships.</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => { setEditing(null); reset({ question: '', answer: '' }); setDialogOpen(true); }} className="px-5 py-2.5 rounded-xl text-white font-semibold flex items-center gap-2 shadow-md hover:opacity-90 transition-opacity" style={{ background: "var(--brand-gradient)" }}>
            <Plus size={16} /> Add FAQ
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Main List */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm flex flex-wrap items-center gap-3">
            <div className="flex-1 min-w-[240px] relative">
              <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={search} onChange={(e) => { setSearch(e.target.value); setSemanticResults([]); }}
                onKeyDown={(e) => e.key === 'Enter' && semanticMode && handleSemanticSearch()}
                placeholder={semanticMode ? "Describe concept to find matches..." : "Search exactly..."}
                className="w-full pl-11 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all text-sm font-medium"
              />
            </div>
            <button
              onClick={() => setSemanticMode(!semanticMode)}
              className={`px-4 py-2.5 rounded-lg flex items-center gap-2 font-semibold text-sm transition-all ${semanticMode ? 'bg-purple-100 text-purple-700 border border-purple-200' : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'}`}
            >
              <Sparkles size={14} className={semanticMode ? "text-purple-600" : ""} /> Semantic Search
            </button>
            {semanticMode && (
              <button onClick={handleSemanticSearch} disabled={isSearching} className="px-5 py-2.5 bg-gray-900 text-white rounded-lg text-sm font-semibold disabled:opacity-50 flex items-center gap-2">
                {isSearching ? <Loader2 size={14} className="animate-spin" /> : "Search"}
              </button>
            )}
          </div>

          {semanticMode && semanticResults.length > 0 && (
            <div className="bg-purple-50 rounded-xl p-5 border border-purple-100 shadow-inner">
              <h4 className="text-sm font-bold text-purple-900 mb-3 flex items-center gap-2"><Sparkles size={16} /> Semantic Matches</h4>
              <div className="space-y-3">
                {semanticResults.map((r, i) => (
                  <div key={i} className="bg-white p-4 rounded-lg border border-purple-100 shadow-sm flex items-start justify-between gap-4">
                    <div>
                      <p className="font-bold text-sm text-gray-900">{r.question}</p>
                      <p className="text-sm text-gray-600 mt-1 line-clamp-2">{r.answer}</p>
                    </div>
                    <span className="shrink-0 px-2.5 py-1 bg-green-100 text-green-700 rounded-full text-xs font-bold border border-green-200">
                      {(r.score * 100).toFixed(1)}% Match
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            {isLoading ? <div className="p-6 text-center text-gray-500"><Loader2 className="animate-spin mx-auto mb-2" /> Loading Knowledge Base...</div> : (
              <div className="divide-y divide-gray-100 max-h-[600px] overflow-y-auto">
                {filtered.map((faq) => (
                  <div key={faq.question} className="p-5 hover:bg-gray-50/80 transition-colors group flex items-start justify-between gap-6">
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-bold text-gray-900 mb-1.5">{faq.question}</h4>
                      <p className="text-sm text-gray-600 leading-relaxed">{faq.answer}</p>
                    </div>
                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                      <button onClick={() => { setEditing(faq); reset({ question: faq.question, answer: faq.answer }); setDialogOpen(true); }} className="w-8 h-8 flex items-center justify-center rounded-md bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors"><Pencil size={14} /></button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild><button className="w-8 h-8 flex items-center justify-center rounded-md bg-red-50 text-red-600 hover:bg-red-100 transition-colors"><Trash2 size={14} /></button></AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete FAQ?</AlertDialogTitle>
                            <AlertDialogDescription>This removes the node and its vector embeddings from Neo4j.</AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction onClick={() => deleteMut.mutate(faq.question)} className="bg-red-600 hover:bg-red-700 text-white">Delete</AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </div>
                ))}
                {!filtered.length && <div className="p-12 text-center text-gray-500 font-medium flex flex-col items-center"><Database size={32} className="mb-3 text-gray-300" /> No FAQs found.</div>}
              </div>
            )}
          </div>
        </div>

        {/* Right Sidebar: Ingestion */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <Upload className="text-cyan-600" size={18} />
              <h3 className="text-base font-bold text-gray-900">Batch Ingest</h3>
            </div>
            <p className="text-xs text-gray-500 mb-4 leading-relaxed">Paste bulk data using the <code className="bg-gray-100 px-1 rounded text-pink-600">Question | Answer</code> format per line. The system will automatically embed and link topics in the graph.</p>
            <textarea
              value={batchText} onChange={(e) => setBatchText(e.target.value)}
              placeholder="What is the ROI? | ROI starts at 8.5% p.a."
              rows={8}
              className="w-full bg-slate-900 text-green-400 font-mono text-xs p-4 rounded-xl focus:outline-none focus:ring-2 focus:ring-cyan-500 resize-none shadow-inner"
            />
            {ingestProgress && (
              <div className="mt-4 p-3 bg-indigo-50 border border-indigo-100 rounded-lg">
                <div className="flex items-center gap-2 text-indigo-700 text-xs font-bold mb-2">
                  <Loader2 size={14} className="animate-spin" /> {ingestProgress}
                </div>
                <Progress value={undefined} className="h-1.5 bg-indigo-200" />
              </div>
            )}
            <button onClick={handleBatchIngest} disabled={!batchText.trim() || !!ingestProgress} className="w-full mt-4 py-2.5 bg-gray-900 hover:bg-gray-800 text-white text-sm font-bold rounded-lg disabled:opacity-50 transition-colors">
              Execute Pipeline
            </button>
          </div>

          <div className="bg-rose-50 rounded-xl p-6 border border-rose-100">
            <h3 className="text-sm font-bold text-rose-800 mb-2 flex items-center gap-2"><AlertTriangle size={16} /> Danger Zone</h3>
            <p className="text-xs text-rose-600 mb-4">Wipe the entire Knowledge Base graph and vector store. Cannot be undone.</p>
            <button className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-lg w-full transition-colors">
              Purge Database
            </button>
          </div>
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold">{editing ? 'Edit Content Node' : 'Create Content Node'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit((d) => saveMut.mutate(d))} className="space-y-5 mt-4">
            <div className="space-y-2">
              <label className="text-sm font-bold text-gray-700">Question</label>
              <input {...register('question', { required: true })} className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-500 text-sm" placeholder="Enter query..." />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-bold text-gray-700">Answer</label>
              <textarea {...register('answer', { required: true })} rows={6} className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-500 text-sm resize-none" placeholder="Provide factual response..." />
            </div>
            <DialogFooter className="pt-2 border-t border-gray-100">
              <button type="button" onClick={() => setDialogOpen(false)} className="px-4 py-2 text-sm font-semibold text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button type="submit" disabled={saveMut.isPending} className="px-6 py-2 text-sm font-bold text-white rounded-lg disabled:opacity-50" style={{ background: "var(--brand-gradient)" }}>
                {saveMut.isPending ? 'Committing...' : 'Commit to Graph'}
              </button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
