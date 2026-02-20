// src/app/components/admin/trace/GlobalTraceSheet.tsx
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { fetchEvalTrace } from '../../../../shared/api/admin'
import { Sheet, SheetContent, SheetTitle } from '../../ui/sheet'
import { TraceTree } from './TraceTree'
import { TraceInspector } from './TraceInspector'
import { parseToLangsmithTree } from './parse'
import type { TraceDetail } from './types'

export function GlobalTraceSheet() {
  const [searchParams, setSearchParams] = useSearchParams()
  const traceId = searchParams.get('traceId')
  const [selectedNodeId, setSelectedNodeId] = useState<string>('root')

  const { data: detail, isLoading } = useQuery({
    queryKey: ['eval-trace', traceId],
    queryFn: () => fetchEvalTrace(traceId!),
    enabled: !!traceId,
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

  return (
    <Sheet open={!!traceId} onOpenChange={(open) => !open && handleClose()}>
      <SheetContent
        side="right"
        aria-describedby={undefined}
        className="w-[100vw] sm:max-w-none p-0 flex flex-col bg-background shadow-2xl border-l border-border [&>button]:hidden"
      >
        <SheetTitle className="sr-only">Trace Viewer</SheetTitle>

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
      </SheetContent>
    </Sheet>
  )
}