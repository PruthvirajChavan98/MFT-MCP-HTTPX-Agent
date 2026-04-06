import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { fetchAdminTrace } from '@features/admin/api/admin'
import { useAdminContext } from '@features/admin/context/AdminContext'
import { buildConversationHref, clearTraceIdSearchParams } from '@features/admin/lib/admin-links'
import { mapTraceDetailToViewer } from '@features/admin/traces/viewmodel'
import { Sheet, SheetContent, SheetTitle } from '@components/ui/sheet'
import { SplitPane } from '@components/ui/split-pane'
import { TraceTree } from './TraceTree'
import { TraceInspector } from './TraceInspector'
import { parseToLangsmithTree } from './parse'

export function GlobalTraceSheet() {
  const [searchParams, setSearchParams] = useSearchParams()
  const traceId = searchParams.get('traceId')
  const [selectedNodeId, setSelectedNodeId] = useState<string>('root')
  const auth = useAdminContext()

  const { data: detail, isLoading } = useQuery({
    queryKey: ['admin-trace', traceId, auth.adminKey],
    queryFn: () => fetchAdminTrace(auth.adminKey, traceId!),
    enabled: !!traceId,
  })

  useEffect(() => {
    setSelectedNodeId('root')
  }, [traceId])

  const handleClose = () => {
    setSearchParams((prev) => clearTraceIdSearchParams(prev), { replace: true })
  }

  const traceDetail = mapTraceDetailToViewer(detail)
  const nodes = traceDetail ? parseToLangsmithTree(traceDetail) : []
  // On desktop, fallback to first node for immediate display.
  // On mobile, require explicit selection so SplitPane shows tree first.
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768
  const selectedNode = selectedNodeId === 'root' && isMobile
    ? null
    : (nodes.find(n => n.id === selectedNodeId) || nodes[0] || null)
  const sessionId = typeof detail?.trace?.session_id === 'string' ? detail.trace.session_id : undefined
  const conversationHref = buildConversationHref(sessionId)

  return (
    <Sheet open={!!traceId} onOpenChange={(open) => !open && handleClose()}>
      <SheetContent
        side="right"
        aria-describedby={undefined}
        className="w-full sm:max-w-none p-0 flex flex-col bg-background shadow-2xl border-l border-border [&>button]:hidden"
      >
        <SheetTitle className="sr-only">Trace Viewer</SheetTitle>

        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="border-b border-border px-4 py-2.5 flex items-center justify-between bg-card">
            <span className="text-xs text-muted-foreground font-medium truncate max-w-[200px] sm:max-w-none">
              Trace {traceId}
            </span>
            {conversationHref && (
              <Link
                to={conversationHref}
                className="inline-flex items-center rounded-md border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-xs font-semibold text-cyan-700 transition hover:bg-cyan-100"
              >
                View Conversation
              </Link>
            )}
          </div>
          <SplitPane
            sidebarWidth="w-[380px]"
            showMain={selectedNodeId !== 'root'}
            onBack={() => setSelectedNodeId('root')}
            className="flex-1 overflow-hidden"
            sidebar={
              <TraceTree
                nodes={nodes}
                selectedNodeId={selectedNodeId}
                onSelect={setSelectedNodeId}
                onClose={handleClose}
                isLoading={isLoading}
              />
            }
            main={
              <TraceInspector node={selectedNode} evals={traceDetail?.evals} shadowJudge={traceDetail?.shadow_judge} />
            }
          />
        </div>
      </SheetContent>
    </Sheet>
  )
}
