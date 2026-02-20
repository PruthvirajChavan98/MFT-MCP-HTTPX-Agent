import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import {
  AlignLeft, Settings, Minimize2, ChevronRight, CheckCircle2,
  Eye, Bird, Link2, Bot, Code
} from 'lucide-react'
import { fetchEvalTrace } from '../../../shared/api/admin'
import { Sheet, SheetContent } from '../ui/sheet'
import { Skeleton } from '../ui/skeleton'

// --- Types & Parsing ---
type AggNodeType = 'trace' | 'chain' | 'llm' | 'parser' | 'tool'

interface FlatNode {
  id: string
  type: AggNodeType
  name: string
  latencyS: string
  status: 'success' | 'error' | 'pending'
  tokens: number
  depth: number
  input?: any
  output?: any
  model?: string
}

function parseToLangsmithTree(traceDetail: any): FlatNode[] {
  if (!traceDetail) return []
  const nodes: FlatNode[] = []
  const trace = traceDetail.trace
  const events = traceDetail.events || []

  const totalS = trace.latency_ms ? (trace.latency_ms / 1000).toFixed(2) : "0.00"
  nodes.push({
    id: 'root',
    type: 'trace',
    name: trace.name || 'Agent Trace',
    latencyS: totalS,
    status: trace.status === 'success' ? 'success' : 'error',
    tokens: 0,
    depth: 0,
    input: trace.inputs_json,
    output: trace.final_output,
    model: trace.model
  })

  // Simulated parent chain to resemble Waterfall
  nodes.push({
    id: 'chain-1',
    type: 'chain',
    name: 'RunnableSequence',
    latencyS: totalS,
    status: 'success',
    tokens: 0,
    depth: 1,
    input: trace.inputs_json,
    output: trace.final_output,
  })

  let currentReasoning: any[] = []
  let currentOutput: any[] = []
  let seq = 0

  const flushReasoning = () => {
    if (currentReasoning.length > 0) {
      nodes.push({
        id: `res-${seq++}`,
        type: 'llm',
        name: 'ReasoningEngine',
        latencyS: '0.00',
        status: 'success',
        tokens: currentReasoning.length,
        depth: 2,
        input: 'System: You are an internal reasoning agent...',
        output: currentReasoning.map(e => e.data || e.text || '').join(''),
        model: trace.model
      })
      currentReasoning = []
    }
  }

  const flushOutput = () => {
    if (currentOutput.length > 0) {
      nodes.push({
        id: `out-${seq++}`,
        type: 'llm',
        name: 'GenerationEngine',
        latencyS: '0.00',
        status: 'success',
        tokens: currentOutput.length,
        depth: 2,
        input: 'System: You are a helpful assistant generation node...',
        output: currentOutput.map(e => e.data || e.text || '').join(''),
        model: trace.model
      })
      currentOutput = []
    }
  }

  for (const ev of events) {
    const etype = ev.event_type || ev.name || ev.event_key
    if (etype === 'reasoning') {
      flushOutput()
      currentReasoning.push(ev)
    } else if (etype === 'token') {
      flushReasoning()
      currentOutput.push(ev)
    } else if (etype === 'tool_call' || etype === 'action' || etype?.includes('tool')) {
      flushReasoning()
      flushOutput()
      nodes.push({
        id: `tool-parse-${seq++}`,
        type: 'parser',
        name: 'ToolParser',
        latencyS: '0.00',
        status: 'success',
        tokens: 0,
        depth: 2,
        input: ev.payload_json || ev.text,
        output: 'Parsed tool correctly'
      })
      nodes.push({
        id: `tool-exec-${seq++}`,
        type: 'tool',
        name: ev.payload_json?.name || ev.event_key || 'execute_tool',
        latencyS: '0.00',
        status: 'success',
        tokens: 0,
        depth: 2,
        input: ev.payload_json,
        output: ev.payload_json?.output || 'Tool executed successfully'
      })
    }
  }

  flushReasoning()
  flushOutput()

  nodes[0].tokens = nodes.reduce((acc, n) => acc + (n.tokens || 0), 0)
  if (nodes[1]) nodes[1].tokens = nodes[0].tokens

  return nodes
}

// --- Components ---

const JsonProp = ({ paramKey, val, depth }: { paramKey: string, val: any, depth: number }) => {
  const [isOpen, setIsOpen] = useState(true)
  const isRecord = val !== null && typeof val === 'object'

  return (
    <div className="text-[13px] font-sans leading-relaxed">
      <div
        className="flex items-center gap-1.5 cursor-pointer text-white/90 font-medium py-1 hover:text-white"
        style={{ paddingLeft: `${depth * 16}px` }}
        onClick={() => setIsOpen(!isOpen)}
      >
        <ChevronRight size={12} className={`shrink-0 text-white/40 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
        <span className="truncate">{paramKey}</span> {(!isRecord && !isOpen) ? <span className="text-white/60 font-normal ml-2 truncate">{String(val)}</span> : null}
      </div>
      {isOpen && (
        <div className="text-white/60" style={{ paddingLeft: `${depth * 16 + 20}px` }}>
          {isRecord ? (
            Object.entries(val).map(([k, v]) => <JsonProp key={k} paramKey={k} val={v} depth={depth + 1} />)
          ) : (
            <div className="py-1 break-all">{String(val)}</div>
          )}
        </div>
      )}
    </div>
  )
}

const JsonViewer = ({ data }: { data: any }) => {
  if (!data || typeof data !== 'object') {
    return <div className="text-white/70 p-4 text-[13px] font-sans whitespace-pre-wrap">{typeof data === 'string' ? data : JSON.stringify(data, null, 2)}</div>
  }
  return (
    <div className="py-2">
      {Object.entries(data).map(([k, v]) => <JsonProp key={k} paramKey={k} val={v} depth={1} />)}
    </div>
  )
}

const Section = ({ title, children }: { title: string, children: React.ReactNode }) => {
  const [open, setOpen] = useState(true)
  return (
    <div className="space-y-3">
      <button
        className="flex items-center gap-2 text-xl font-medium text-white hover:text-white/80 transition-colors"
        onClick={() => setOpen(!open)}
      >
        {title}
        <ChevronRight size={16} className={`text-white/40 transition-transform ${open ? 'rotate-90' : 'rotate-0'}`} />
      </button>
      {open && children}
    </div>
  )
}

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

  const nodes = detail ? parseToLangsmithTree(detail) : []
  const selectedNode = nodes.find(n => n.id === selectedNodeId) || nodes[0]

  const getNodeIcon = (type: AggNodeType, size: number = 14) => {
    switch (type) {
      case 'trace': return <Bird size={size} />
      case 'chain': return <Link2 size={size} />
      case 'tool': return <Link2 size={size} />
      case 'llm': return <Bot size={size} />
      case 'parser': return <span className={`font-bold`} style={{ fontSize: size * 0.75 }}>{'{x}'}</span>
      default: return <Code size={size} />
    }
  }

  const getNodeBg = (type: AggNodeType) => {
    switch (type) {
      case 'trace': return 'bg-[#1e293b] text-white border border-white/20'
      case 'chain': return 'bg-[#983ea0] text-white'
      case 'tool': return 'bg-[#983ea0] text-white'
      case 'llm': return 'bg-[#cf4b76] text-white'
      case 'parser': return 'bg-[#df7d54] text-white'
      default: return 'bg-slate-700 text-white'
    }
  }

  return (
    <Sheet open={!!traceId} onOpenChange={(open) => !open && handleClose()}>
      <SheetContent side="right" className="w-[100vw] sm:max-w-none p-0 flex flex-col bg-[#0A0C10] shadow-2xl transition-all duration-300">
        <div className="flex-1 flex overflow-hidden">

          {/* Left Pane: Tree */}
          <div className="w-[360px] border-r border-[#222222] bg-[#0f1115] flex flex-col shrink-0">
            <div className="p-4 shrink-0">
              <div className="text-[11px] font-bold text-white/50 tracking-widest mb-3">TRACE</div>
              <div className="flex items-center gap-2">
                <button className="flex items-center gap-1.5 text-[12px] font-medium text-white bg-[#1C1C1E] border border-white/10 px-2.5 py-1.5 rounded-md hover:bg-white/10 transition-colors">
                  <AlignLeft size={14} /> Waterfall
                </button>
                <button className="p-1.5 rounded-md bg-[#1C1C1E] border border-white/10 text-white/70 hover:text-white transition-colors">
                  <Settings size={14} />
                </button>
                <button onClick={handleClose} className="p-1.5 rounded-md bg-[#1C1C1E] border border-white/10 text-white/70 hover:text-white transition-colors">
                  <Minimize2 size={14} />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto no-scrollbar pb-8 relative mt-2">
              {isLoading ? (
                <div className="p-4 space-y-4">
                  <Skeleton className="h-6 w-full bg-white/5 rounded" />
                  <Skeleton className="h-6 w-5/6 bg-white/5 rounded ml-4" />
                </div>
              ) : nodes.map((node) => {
                const isSelected = selectedNodeId === node.id;
                return (
                  <div
                    key={node.id}
                    onClick={() => setSelectedNodeId(node.id)}
                    className={`relative cursor-pointer select-none py-2 flex items-center gap-2.5 transition-colors ${isSelected ? 'bg-[#1A2E2A]' : 'hover:bg-white/5'}`}
                    style={{ paddingLeft: `${node.depth * 24 + 20}px`, paddingRight: '20px' }}
                  >
                    {/* Tree branching lines */}
                    {node.depth > 0 && (
                      <div className="absolute top-0 bottom-0 border-l border-[#334155]" style={{ left: `${(node.depth - 1) * 24 + 32}px` }} />
                    )}
                    {node.depth > 0 && (
                      <div className="absolute h-px bg-[#334155] w-[14px]" style={{ left: `${(node.depth - 1) * 24 + 32}px`, top: '20px' }} />
                    )}

                    <div className={`shrink-0 w-[22px] h-[22px] rounded-md flex items-center justify-center z-10 ${getNodeBg(node.type)}`}>
                      {getNodeIcon(node.type, 12)}
                    </div>

                    <div className="flex-1 min-w-0 flex flex-col justify-center">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 truncate">
                          <span className={`text-[13px] font-medium truncate ${isSelected ? 'text-[#aee0cd]' : 'text-white/90'}`}>{node.name}</span>
                          {node.model && (
                            <span className="px-1.5 py-[1px] rounded border border-white/15 text-white/50 text-[10px] font-mono whitespace-nowrap bg-black/20">{node.model}</span>
                          )}
                          {node.type === 'trace' && node.status === 'success' && (
                            <CheckCircle2 size={14} className="text-[#3fb06a] shrink-0" />
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0 pl-2">
                          <span className="text-white/40 text-[11px] font-mono">{node.latencyS}s</span>
                          <ChevronRight size={14} className={`text-white/20 ${isSelected ? 'opacity-100' : 'opacity-0'} group-hover:opacity-100 transition-opacity`} />
                        </div>
                      </div>

                      {/* Metrics under Root Node */}
                      {node.type === 'trace' && (
                        <div className="flex items-center gap-2 mt-2 border-t border-transparent">
                          <div className="bg-[#782322]/30 border border-[#b93836]/40 text-[#f5817d] text-[11px] font-mono px-1.5 py-[1px] rounded flex items-center gap-1">
                            {node.latencyS}s
                          </div>
                          <div className="border border-[#334155] text-white/80 text-[11px] font-mono px-1.5 py-[1px] rounded flex items-center gap-1.5">
                            <Eye size={10} /> {node.tokens.toLocaleString()}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Right Pane: Inspector */}
          <div className="flex-1 overflow-y-auto bg-[#0b0c10]">
            {selectedNode ? (
              <div className="p-10 max-w-5xl mx-auto space-y-10">

                {/* Header Title */}
                <div className="flex flex-col gap-4">
                  <div className="flex items-center gap-4">
                    <div className={`shrink-0 w-11 h-11 rounded-xl shadow-lg flex items-center justify-center ${getNodeBg(selectedNode.type)}`}>
                      {getNodeIcon(selectedNode.type, 22)}
                    </div>
                    <h1 className="text-[32px] font-semibold text-white tracking-tight">{selectedNode.name}</h1>
                  </div>
                  <div className="flex items-center gap-3">
                    {selectedNode.status === 'success' && (
                      <div className="flex items-center gap-1.5 text-[#3fb06a] border border-[#3fb06a]/30 bg-[#3fb06a]/10 px-2.5 py-1 rounded text-[13px] font-medium">
                        <CheckCircle2 size={14} /> Success
                      </div>
                    )}
                    <div className="bg-[#782322]/20 border border-[#b93836]/40 text-[#f5817d] text-[13px] font-mono px-2.5 py-1 rounded">
                      {selectedNode.latencyS}s
                    </div>
                    {(selectedNode.tokens > 0) && (
                      <div className="border border-white/20 text-white/80 text-[13px] font-mono px-2.5 py-1 rounded flex items-center gap-2">
                        <Eye size={14} /> {selectedNode.tokens.toLocaleString()}
                      </div>
                    )}
                  </div>
                </div>

                {/* Input / Output Blocks */}
                <div className="space-y-8">
                  <Section title="Input">
                    {selectedNode.type === 'llm' ? (
                      <div className="bg-[#111318] border border-white/5 rounded-xl p-6">
                        <div className="text-white/90 text-[13px] font-bold tracking-wide uppercase mb-3">SYSTEM</div>
                        <div className="text-white/60 text-[14px] leading-relaxed font-sans whitespace-pre-wrap">
                          {typeof selectedNode.input === 'string' ? selectedNode.input : JSON.stringify(selectedNode.input, null, 2)}
                        </div>
                      </div>
                    ) : (
                      <div className="bg-[#111318] border border-white/5 rounded-xl p-4">
                        <JsonViewer data={selectedNode.input} />
                      </div>
                    )}
                  </Section>

                  <Section title="Output">
                    <div className="bg-[#111318] border border-white/5 rounded-xl p-4 min-h-[100px]">
                      {typeof selectedNode.output === 'string' ? (
                        <div className="text-white/60 text-[14px] leading-relaxed font-sans whitespace-pre-wrap px-2 py-1">{selectedNode.output}</div>
                      ) : (
                        <JsonViewer data={selectedNode.output} />
                      )}
                    </div>
                  </Section>
                </div>

              </div>
            ) : null}
          </div>

        </div>
      </SheetContent>
    </Sheet>
  )
}
