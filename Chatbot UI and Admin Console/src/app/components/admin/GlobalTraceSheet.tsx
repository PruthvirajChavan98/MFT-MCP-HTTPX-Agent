import { useEffect } from 'react'
import { useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { BrainCircuit, XCircle, CheckCircle2 } from 'lucide-react'
import { fetchEvalTrace } from '../../../shared/api/admin'
import { toPrettyJson } from '../../../shared/lib/json'
import { formatDateTime } from '../../../shared/lib/format'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '../ui/sheet'
import { Skeleton } from '../ui/skeleton'

export function GlobalTraceSheet() {
  const [searchParams, setSearchParams] = useSearchParams()
  const traceId = searchParams.get('traceId')

  const { data: detail, isLoading, error } = useQuery({
    queryKey: ['eval-trace', traceId],
    queryFn: () => fetchEvalTrace(traceId!),
    enabled: !!traceId,
  })

  const handleClose = () => {
    setSearchParams((prev) => {
      prev.delete('traceId')
      return prev
    })
  }

  return (
    <Sheet open={!!traceId} onOpenChange={(open) => !open && handleClose()}>
      <SheetContent side="right" className="w-full sm:max-w-3xl overflow-y-auto bg-slate-50 p-0">
        <SheetHeader className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
              <BrainCircuit size={20} />
            </div>
            <div className="text-left">
              <SheetTitle className="text-base font-semibold">Trace Details</SheetTitle>
              <SheetDescription className="font-mono text-xs text-slate-500">
                {traceId}
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        <div className="p-6 space-y-6">
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-24 w-full rounded-xl" />
              <Skeleton className="h-48 w-full rounded-xl" />
            </div>
          ) : error ? (
            <div className="p-4 bg-red-50 text-red-600 rounded-xl border border-red-100 text-sm">
              Error loading trace: {(error as Error).message}
            </div>
          ) : detail ? (
            <>
              {/* Metadata Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  ['Status', detail.trace.status === 'success' ? (
                    <span className="flex items-center gap-1 text-emerald-600"><CheckCircle2 size={14}/> Success</span>
                  ) : (
                    <span className="flex items-center gap-1 text-red-600"><XCircle size={14}/> {detail.trace.status}</span>
                  )],
                  ['Model', detail.trace.model ?? '—'],
                  ['Latency', detail.trace.latency_ms ? `${detail.trace.latency_ms}ms` : '—'],
                  ['Started', formatDateTime(detail.trace.started_at)],
                ].map(([label, val], i) => (
                  <div key={i} className="bg-white rounded-xl p-3 border border-slate-200 shadow-sm">
                    <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">{label}</p>
                    <div className="mt-1 text-sm font-medium text-slate-700 truncate">{val}</div>
                  </div>
                ))}
              </div>

              {/* I/O Section */}
              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm flex flex-col">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Inputs</h3>
                  <div className="flex-1 bg-slate-900 rounded-lg p-3 overflow-x-auto">
                    <pre className="text-xs text-green-400 font-mono">
                      {toPrettyJson(detail.trace.inputs_json)}
                    </pre>
                  </div>
                </div>
                
                <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm flex flex-col">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Final Output</h3>
                  <div className="flex-1 text-sm text-slate-700 leading-relaxed bg-slate-50 rounded-lg p-3 border border-slate-100 whitespace-pre-wrap">
                    {detail.trace.final_output || <span className="text-slate-400 italic">No output generated</span>}
                  </div>
                </div>
              </div>

              {/* Events Timeline */}
              {detail.events.length > 0 && (
                <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Execution Events</h3>
                  <div className="space-y-3 relative before:absolute before:inset-y-0 before:left-3 before:w-px before:bg-slate-200">
                    {detail.events.map((ev, i) => (
                      <div key={i} className="relative pl-8">
                        <div className="absolute left-[9px] top-1.5 w-2 h-2 rounded-full bg-indigo-500 ring-4 ring-white" />
                        <div className="bg-slate-50 rounded-lg border border-slate-100 p-3">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-bold text-slate-700">{ev.name ?? ev.event_type ?? ev.event_key}</span>
                            <span className="text-[10px] text-slate-400 font-mono">{ev.ts ? formatDateTime(ev.ts) : ''}</span>
                          </div>
                          {ev.text && <p className="text-xs text-slate-600 mb-2">{ev.text}</p>}
                          {ev.payload_json && (
                            <pre className="text-[10px] bg-slate-900 text-slate-300 rounded p-2 overflow-x-auto max-h-40">
                              {toPrettyJson(ev.payload_json)}
                            </pre>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  )
}