import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { fetchConversations, extractTraceQuestion } from '../../../shared/api/admin'
import { useAdminContext } from './AdminContext'
import { Card, CardContent } from '../ui/card'
import { Input } from '../ui/input'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '../ui/resizable'
import { ScrollArea } from '../ui/scroll-area'
import { formatDateTime } from '../../../shared/lib/format'

export function Conversations() {
  const auth = useAdminContext()
  const [search, setSearch] = useState('')
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)

  const { data = [], isLoading, error } = useQuery({
    queryKey: ['conversations', auth.adminKey],
    queryFn: () => fetchConversations(auth.adminKey),
    enabled: !!auth.adminKey,
  })

  const filtered = data.filter((c) => !search || extractTraceQuestion(c).toLowerCase().includes(search.toLowerCase()) || c.session_id.includes(search))
  const selected = selectedIdx !== null ? filtered[selectedIdx] : null

  if (!auth.adminKey) return <Alert><AlertDescription>Set X-Admin-Key to view conversations.</AlertDescription></Alert>
  if (error) return <Alert variant="destructive"><AlertDescription>{(error as Error).message}</AlertDescription></Alert>

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Conversations</h1>
      <div className="relative max-w-sm">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input placeholder="Search…" className="pl-8 h-8 text-sm" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      <Card className="overflow-hidden" style={{ height: 'calc(100vh - 280px)', minHeight: 400 }}>
        {/* @ts-expect-error - direction prop exists at runtime */}
        <ResizablePanelGroup direction="horizontal" className="h-full">
          <ResizablePanel defaultSize={40} minSize={25}>
            <ScrollArea className="h-full">
              {isLoading ? <div className="p-3 space-y-2">{Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="h-16 rounded" />)}</div> : (
                <div className="p-2 space-y-1">
                  {filtered.map((c, i) => (
                    <button key={c.trace_id} onClick={() => setSelectedIdx(i)} className={`w-full text-left p-3 rounded-lg border transition-colors ${selectedIdx === i ? 'bg-cyan-50 border-cyan-200' : 'bg-white border-transparent hover:bg-slate-50'}`}>
                      <p className="font-mono text-xs text-slate-400 truncate">{c.session_id}</p>
                      <p className="text-sm font-medium text-slate-700 mt-0.5 line-clamp-2">{extractTraceQuestion(c) || '—'}</p>
                      <p className="text-[10px] text-slate-400 mt-1">{formatDateTime(c.started_at)}</p>
                    </button>
                  ))}
                  {!filtered.length && <p className="p-4 text-sm text-muted-foreground text-center">No conversations</p>}
                </div>
              )}
            </ScrollArea>
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize={60} minSize={40}>
            <ScrollArea className="h-full">
              {!selected ? (
                <div className="flex items-center justify-center h-full text-sm text-muted-foreground">Select a conversation</div>
              ) : (
                <div className="p-4 space-y-3">
                  <div className="text-xs text-muted-foreground space-y-0.5">
                    <p>Session: <span className="font-mono">{selected.session_id}</span></p>
                    <p>Model: {selected.model ?? '—'} · {formatDateTime(selected.started_at)}</p>
                  </div>
                  <div className="space-y-3">
                    {selected.inputs_json && (
                      <div className="flex gap-2">
                        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-cyan-100 text-cyan-700 flex items-center justify-center text-xs font-bold">U</span>
                        <div className="bg-cyan-50 border border-cyan-100 rounded-xl px-3 py-2 text-sm text-slate-700 flex-1">{extractTraceQuestion(selected)}</div>
                      </div>
                    )}
                    {selected.final_output && (
                      <div className="flex gap-2">
                        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center text-xs font-bold">A</span>
                        <div className="bg-white border border-slate-200 rounded-xl px-3 py-2 text-sm text-slate-700 flex-1 leading-relaxed">{selected.final_output}</div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </ScrollArea>
          </ResizablePanel>
        </ResizablePanelGroup>
      </Card>
    </div>
  )
}
