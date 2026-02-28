// src/app/components/admin/trace/GlobalTraceSheet.tsx
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { fetchAdminTrace } from '../../../../shared/api/admin'
import { useAdminContext } from '../AdminContext'
import { Sheet, SheetContent, SheetTitle } from '../../ui/sheet'
import { TraceTree } from './TraceTree'
import { TraceInspector } from './TraceInspector'
import { parseToLangsmithTree } from './parse'
import type { TraceDetail } from './types'
import { buildConversationHref } from '../../../../shared/lib/admin-links'

export function GlobalTraceSheet() {
  const [searchParams, setSearchParams] = useSearchParams()
  const traceId = searchParams.get('traceId')
  const [selectedNodeId, setSelectedNodeId] = useState<string>('root')
  const auth = useAdminContext()
  const hasAdminKey = !!auth.adminKey.trim()

  const { data: detail, isLoading } = useQuery({
    queryKey: ['admin-trace', traceId, auth.adminKey],
    queryFn: () => fetchAdminTrace(auth.adminKey, traceId!),
    enabled: !!traceId && hasAdminKey,
  })

  useEffect(() => {
    setSelectedNodeId('root')
  }, [traceId])

  const handleClose = () => {
    setSearchParams((prev) => {
      prev.delete('traceId')
      return prev
    })
  }

  // Parse and cast API trace structure to match the viewer
  const nodes = detail ? parseToLangsmithTree(detail as unknown as TraceDetail) : []
  const selectedNode = nodes.find(n => n.id === selectedNodeId) || nodes[0] || null
  const sessionId = typeof detail?.trace?.session_id === 'string' ? detail.trace.session_id : undefined
  const conversationHref = buildConversationHref(sessionId)

  return (
    <Sheet open={!!traceId} onOpenChange={(open) => !open && handleClose()}>
      <SheetContent
        side="right"
        aria-describedby={undefined}
        className="w-[100vw] sm:max-w-none p-0 flex flex-col bg-background shadow-2xl border-l border-border [&>button]:hidden"
      >
        <SheetTitle className="sr-only">Trace Viewer</SheetTitle>

        {!hasAdminKey ? (
          <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
            Admin API key is required to inspect traces.
          </div>
        ) : (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="border-b border-border px-4 py-2.5 flex items-center justify-between bg-card">
              <span className="text-xs text-muted-foreground font-medium">
                Trace {traceId}
              </span>
              {conversationHref ? (
                <Link
                  to={conversationHref}
                  className="inline-flex items-center rounded-md border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-xs font-semibold text-cyan-700 transition hover:bg-cyan-100"
                >
                  View Conversation
                </Link>
              ) : (
                <span className="text-[11px] text-muted-foreground">Conversation unavailable</span>
              )}
            </div>
            <div className="flex-1 flex overflow-hidden">
            <TraceTree
              nodes={nodes}
              selectedNodeId={selectedNodeId}
              onSelect={setSelectedNodeId}
              onClose={handleClose}
              isLoading={isLoading}
            />
            <TraceInspector
              node={selectedNode}
              cost={(detail as any)?.cost}
            />
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
