// src/app/components/admin/trace/TraceInspector.tsx
import { useState } from 'react'
import type { ReactNode } from 'react'
import {
  CheckCircle2, AlertCircle, Eye, ChevronRight,
  DollarSign, Zap, BarChart3, Cpu,
} from 'lucide-react'
import { getNodeIcon, getNodeChipClasses, getNodeTypeLabel } from './nodeUtils'
import { JsonViewer } from './JsonViewer'
import type { FlatNode, TraceCost } from './types'

interface SectionProps {
  title: string
  children: ReactNode
  defaultOpen?: boolean
  badge?: string
}

function Section({ title, children, defaultOpen = true, badge }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="space-y-2.5">
      <button
        className="flex items-center gap-2 text-foreground hover:text-foreground/70 transition-colors w-full text-left"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="text-[15px] font-medium">{title}</span>
        {badge && (
          <span className="text-[10px] font-mono text-muted-foreground border border-border px-1.5 py-px rounded">
            {badge}
          </span>
        )}
        <ChevronRight
          size={14}
          className={`text-muted-foreground ml-auto transition-transform duration-150 ${open ? 'rotate-90' : ''}`}
        />
      </button>
      {open && (
        <div className="animate-in fade-in-0 slide-in-from-top-1 duration-150">
          {children}
        </div>
      )}
    </div>
  )
}

function CostPanel({ cost }: { cost: TraceCost }) {
  const fmtUSD = (n: number) =>
    n < 0.001 ? `$${(n * 1000).toFixed(4)}m` : `$${n.toFixed(6)}`

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <DollarSign size={13} className="text-muted-foreground" />
          <span className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">Run Cost</span>
        </div>
        <span className="text-[18px] font-semibold text-foreground tabular-nums">
          {fmtUSD(cost.total_cost)}
          <span className="text-[11px] text-muted-foreground font-normal ml-1">{cost.currency}</span>
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-y divide-border">
        <CostCell icon={<Zap size={12} />} label="Prompt" value={cost.usage.prompt_tokens.toLocaleString()} unit="tok" />
        <CostCell icon={<BarChart3 size={12} />} label="Completion" value={cost.usage.completion_tokens.toLocaleString()} unit="tok" />
        {(cost.usage.reasoning_tokens ?? 0) > 0 && (
          <CostCell icon={<Eye size={12} />} label="Reasoning" value={(cost.usage.reasoning_tokens ?? 0).toLocaleString()} unit="tok" />
        )}
        <CostCell icon={<Cpu size={12} />} label="Total" value={cost.usage.total_tokens.toLocaleString()} unit="tok" highlight />
      </div>
      <div className="px-4 py-2 bg-muted/30 border-t border-border flex items-center gap-2">
        <span className="text-[10px] text-muted-foreground font-mono">{cost.model}</span>
        <span className="text-muted-foreground/40">·</span>
        <span className="text-[10px] text-muted-foreground capitalize">{cost.provider}</span>
      </div>
    </div>
  )
}

function CostCell({ icon, label, value, unit, highlight }: { icon: ReactNode, label: string, value: string, unit: string, highlight?: boolean }) {
  return (
    <div className="px-4 py-3 space-y-1">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        {icon}
        <span className="text-[10px] font-medium uppercase tracking-wide">{label}</span>
      </div>
      <div className={`text-[15px] font-semibold tabular-nums ${highlight ? 'text-foreground' : 'text-foreground/80'}`}>
        {value}
        <span className="text-[10px] font-normal text-muted-foreground ml-0.5">{unit}</span>
      </div>
    </div>
  )
}

function SystemPromptCard({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="px-4 py-2 border-b border-border">
        <span className="text-[10px] font-bold tracking-widest text-muted-foreground uppercase">System</span>
      </div>
      <div className="px-4 py-3 text-[13px] text-foreground/80 leading-relaxed whitespace-pre-wrap font-sans">
        {text}
      </div>
    </div>
  )
}

function DataCard({ data }: { data: unknown }) {
  if (typeof data === 'string') {
    return <div className="rounded-xl border border-border bg-card px-4 py-3 text-[13px] text-foreground/80 leading-relaxed whitespace-pre-wrap font-sans min-h-[80px]">{data}</div>
  }
  return <div className="rounded-xl border border-border bg-card min-h-[60px] overflow-hidden"><JsonViewer data={data} /></div>
}

export function TraceInspector({ node, cost }: { node: FlatNode | null, cost?: TraceCost }) {
  if (!node) {
    return <div className="flex-1 flex items-center justify-center text-muted-foreground text-[14px]">Select a node to inspect</div>
  }

  const latencyLabel = node.latencyS === '—' ? '—' : `${node.latencyS}s`
  const showCostPanel = node.type === 'trace' && !!cost

  return (
    <div className="flex-1 overflow-y-auto bg-background">
      <div className="p-8 max-w-4xl mx-auto space-y-8">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className={`shrink-0 w-11 h-11 rounded-xl flex items-center justify-center shadow-sm ${getNodeChipClasses(node.type)}`}>
              {getNodeIcon(node.type, 20)}
            </div>
            <div className="min-w-0">
              <h1 className="text-foreground truncate text-[22px] font-semibold tracking-tight leading-snug">{node.name}</h1>
              <p className="text-muted-foreground text-[12px] mt-0.5">
                {getNodeTypeLabel(node.type)}
                {node.model ? ` · ${node.model}` : ''}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {node.status === 'success' && <span className="flex items-center gap-1 text-emerald-600 border border-emerald-200 bg-emerald-50 px-2.5 py-1 rounded-full text-[12px] font-medium"><CheckCircle2 size={12} /> Success</span>}
            {node.status === 'error' && <span className="flex items-center gap-1 text-rose-600 border border-rose-200 bg-rose-50 px-2.5 py-1 rounded-full text-[12px] font-medium"><AlertCircle size={12} /> Error</span>}
            <span className="border border-rose-200 bg-rose-50 text-rose-600 text-[12px] font-mono px-2.5 py-1 rounded-full">{latencyLabel}</span>
            {node.tokens > 0 && <span className="border border-border bg-muted text-muted-foreground text-[12px] font-mono px-2.5 py-1 rounded-full flex items-center gap-1.5"><Eye size={12} /> {node.tokens.toLocaleString()} tokens</span>}
          </div>
        </div>

        <div className="border-t border-border" />

        {showCostPanel && (
          <Section title="Cost" defaultOpen>
            <CostPanel cost={cost!} />
          </Section>
        )}

        <Section title="Input">
          {node.type === 'llm' ? <SystemPromptCard text={typeof node.input === 'string' ? node.input : JSON.stringify(node.input, null, 2)} /> : <DataCard data={node.input} />}
        </Section>

        <Section title="Output">
          <DataCard data={node.output} />
        </Section>
      </div>
    </div>
  )
}
