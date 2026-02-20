// src/app/components/admin/trace/TraceTree.tsx
import { AlignLeft, Settings, Minimize2, CheckCircle2, Eye, ChevronRight } from 'lucide-react'
import { Skeleton } from '../../ui/skeleton'
import { getNodeIcon, getNodeChipClasses, getBarColor } from './nodeUtils'
import type { FlatNode } from './types'

interface TraceTreeProps {
  nodes: FlatNode[]
  selectedNodeId: string
  onSelect: (id: string) => void
  onClose: () => void
  isLoading: boolean
}

export function TraceTree({ nodes, selectedNodeId, onSelect, onClose, isLoading }: TraceTreeProps) {
  return (
    <div className="w-[380px] border-r border-border bg-card flex flex-col shrink-0 h-full">
      <div className="px-4 pt-4 pb-3 border-b border-border shrink-0 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-muted-foreground tracking-[0.12em] uppercase">
            Trace Explorer
          </span>
          <div className="flex items-center gap-1">
            <button className="p-1.5 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors" aria-label="Settings">
              <Settings size={13} />
            </button>
            <button onClick={onClose} className="p-1.5 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors" aria-label="Close">
              <Minimize2 size={13} />
            </button>
          </div>
        </div>

        <button className="flex items-center gap-1.5 text-[12px] font-medium text-foreground bg-muted border border-border px-2.5 py-1.5 rounded-md hover:bg-accent transition-colors">
          <AlignLeft size={13} /> Waterfall
        </button>
      </div>

      <div className="flex-1 overflow-y-auto pb-8 mt-1">
        {isLoading ? (
          <div className="p-4 space-y-3">
            <Skeleton className="h-10 w-full rounded" />
            <Skeleton className="h-10 w-5/6 rounded ml-5" />
            <Skeleton className="h-10 w-4/6 rounded ml-10" />
            <Skeleton className="h-10 w-4/6 rounded ml-10" />
            <Skeleton className="h-10 w-4/6 rounded ml-10" />
          </div>
        ) : (
          nodes.map((node) => (
            <NodeRow key={node.id} node={node} isSelected={selectedNodeId === node.id} onSelect={onSelect} />
          ))
        )}
      </div>
    </div>
  )
}

function NodeRow({ node, isSelected, onSelect }: { node: FlatNode, isSelected: boolean, onSelect: (id: string) => void }) {
  const indentPx = node.depth * 20 + 16
  const barColor = getBarColor(node.type)

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(node.id)}
      onKeyDown={(e) => e.key === 'Enter' && onSelect(node.id)}
      className={`relative cursor-pointer select-none group transition-colors duration-100 border-l-2 ${isSelected ? 'bg-accent border-l-violet-500' : 'border-l-transparent hover:bg-accent/60'}`}
      style={{ paddingLeft: `${indentPx}px`, paddingRight: '14px' }}
    >
      {node.depth > 0 && <div className="absolute top-0 bottom-0 border-l border-border" style={{ left: `${(node.depth - 1) * 20 + 24}px` }} />}
      {node.depth > 0 && <div className="absolute h-px bg-border" style={{ left: `${(node.depth - 1) * 20 + 24}px`, width: '12px', top: '20px' }} />}

      <div className="flex items-start gap-2.5 py-2">
        <div className={`shrink-0 w-[22px] h-[22px] rounded-md flex items-center justify-center z-10 mt-0.5 ${getNodeChipClasses(node.type)}`}>
          {getNodeIcon(node.type, 11)}
        </div>

        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className={`text-[13px] truncate font-medium ${isSelected ? 'text-foreground' : 'text-foreground/80'}`}>{node.name}</span>
              {node.model && <span className="hidden sm:inline-flex shrink-0 px-1.5 py-px rounded border border-border text-muted-foreground text-[10px] font-mono bg-muted whitespace-nowrap">{node.model.split('/').pop()}</span>}
              {node.type === 'trace' && node.status === 'success' && <CheckCircle2 size={12} className="text-emerald-500 shrink-0" />}
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="text-muted-foreground text-[11px] font-mono tabular-nums">{node.latencyS}s</span>
              <ChevronRight size={12} className={`text-muted-foreground transition-opacity ${isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-60'}`} />
            </div>
          </div>

          {node.type === 'trace' && (
            <div className="flex items-center gap-1.5">
              <span className="bg-rose-50 border border-rose-200 text-rose-600 text-[10px] font-mono px-1.5 py-px rounded">{node.latencyS}s</span>
              <span className="border border-border text-muted-foreground text-[10px] font-mono px-1.5 py-px rounded flex items-center gap-1">
                <Eye size={9} /> {node.tokens.toLocaleString()} tok
              </span>
            </div>
          )}

          {node.durationPct !== undefined && node.offsetPct !== undefined && (
            <div className="relative h-[3px] rounded-full bg-border overflow-hidden">
              <div
                className="absolute top-0 h-full rounded-full opacity-70"
                style={{
                  left: `${node.offsetPct}%`,
                  width: `${Math.min(node.durationPct, 100 - node.offsetPct)}%`,
                  backgroundColor: barColor,
                }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}