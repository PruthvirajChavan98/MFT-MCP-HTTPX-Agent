import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react'
import { fetchEvalTraces, fetchEvalTrace, extractTraceQuestion } from '../../../shared/api/admin'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Input } from '../ui/input'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '../ui/resizable'
import { ScrollArea } from '../ui/scroll-area'
import { toPrettyJson } from '../../../shared/lib/json'
import { formatDateTime } from '../../../shared/lib/format'

export function ChatTraces() {
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: traces = [], isLoading, error } = useQuery({
    queryKey: ['eval-traces'],
    queryFn: () => fetchEvalTraces(200),
  })

  const { data: detail, isLoading: dLoading } = useQuery({
    queryKey: ['eval-trace', selectedId],
    queryFn: () => fetchEvalTrace(selectedId!),
    enabled: !!selectedId,
  })

  const filtered = traces.filter(
    (t) =>
      !search ||
      t.trace_id.includes(search) ||
      t.session_id.includes(search) ||
      extractTraceQuestion(t).toLowerCase().includes(search.toLowerCase()),
  )

  if (error) return <Alert variant="destructive"><AlertDescription>{(error as Error).message}</AlertDescription></Alert>

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Chat Traces</h1>
      <div className="relative max-w-sm">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input placeholder="Search traces…" className="pl-8 h-8 text-sm" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      <Card className="overflow-hidden" style={{ height: 'calc(100vh - 280px)', minHeight: 400 }}>
        {/* @ts-expect-error - direction prop exists at runtime */}
        <ResizablePanelGroup direction="horizontal" className="h-full">
          {/* Left: trace list */}
          <ResizablePanel defaultSize={35} minSize={25}>
            <ScrollArea className="h-full">
              {isLoading ? (
                <div className="p-3 space-y-2">{Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="h-16 rounded" />)}</div>
              ) : (
                <div className="p-2 space-y-1">
                  {filtered.map((t) => (
                    <button
                      key={t.trace_id}
                      onClick={() => setSelectedId(t.trace_id)}
                      className={`w-full text-left p-3 rounded-lg border transition-colors text-sm ${selectedId === t.trace_id ? 'bg-cyan-50 border-cyan-200' : 'bg-white border-transparent hover:bg-slate-50 hover:border-slate-200'}`}
                    >
                      <p className="font-mono text-xs text-slate-400 truncate">{t.trace_id}</p>
                      <p className="font-medium text-slate-700 text-sm mt-0.5 line-clamp-2">{extractTraceQuestion(t) || t.final_output?.slice(0, 80) || '—'}</p>
                      <div className="flex items-center gap-2 mt-1">
                        {t.error ? <XCircle size={12} className="text-red-500" /> : <CheckCircle2 size={12} className="text-emerald-500" />}
                        <span className="text-[10px] text-slate-400">{t.latency_ms ? `${t.latency_ms}ms` : ''} · {t.model ?? ''}</span>
                      </div>
                    </button>
                  ))}
                  {!filtered.length && <p className="p-4 text-sm text-muted-foreground text-center">No traces found</p>}
                </div>
              )}
            </ScrollArea>
          </ResizablePanel>

          <ResizableHandle withHandle />

          {/* Right: trace detail */}
          <ResizablePanel defaultSize={65} minSize={40}>
            <ScrollArea className="h-full">
              {!selectedId ? (
                <div className="flex items-center justify-center h-full text-sm text-muted-foreground">Select a trace to view details</div>
              ) : dLoading ? (
                <div className="p-4 space-y-3">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-20 rounded" />)}</div>
              ) : detail ? (
                <div className="p-4 space-y-4">
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    {[
                      ['Trace ID', detail.trace.trace_id],
                      ['Session', detail.trace.session_id],
                      ['Model', detail.trace.model ?? '—'],
                      ['Provider', detail.trace.provider ?? '—'],
                      ['Latency', detail.trace.latency_ms ? `${detail.trace.latency_ms}ms` : '—'],
                      ['Started', formatDateTime(detail.trace.started_at)],
                    ].map(([k, v]) => (
                      <div key={k} className="bg-slate-50 rounded-lg p-2 border border-slate-100">
                        <p className="text-muted-foreground font-medium">{k}</p>
                        <p className="font-mono text-slate-700 truncate mt-0.5">{v}</p>
                      </div>
                    ))}
                  </div>

                  {detail.trace.final_output && (
                    <div>
                      <p className="text-xs font-semibold text-slate-600 mb-1">Response</p>
                      <div className="text-sm bg-slate-50 rounded-lg p-3 border border-slate-100 text-slate-700 leading-relaxed">{detail.trace.final_output}</div>
                    </div>
                  )}

                  {/* Events */}
                  {detail.events.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-600 mb-2">Events ({detail.events.length})</p>
                      <div className="space-y-2">
                        {detail.events.map((ev, i) => (
                          <div key={i} className="bg-white rounded-lg border border-slate-200 p-3">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-medium text-slate-700">{ev.name ?? ev.event_type ?? ev.event_key}</span>
                              <span className="text-[10px] text-slate-400 font-mono">{ev.ts ? formatDateTime(ev.ts) : ''}</span>
                            </div>
                            {ev.text && <p className="text-xs text-slate-600">{ev.text}</p>}
                            {ev.payload_json && (
                              <pre className="text-[10px] mt-1 bg-slate-50 rounded p-2 overflow-x-auto text-slate-600 max-h-32">{toPrettyJson(ev.payload_json)}</pre>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : null}
            </ScrollArea>
          </ResizablePanel>
        </ResizablePanelGroup>
      </Card>
    </div>
  )
}
