// src/app/components/admin/trace/nodeUtils.tsx
import React from 'react'
import { Brain, Link2, Bot, Code, Wrench, GitBranch } from 'lucide-react'
import type { AggNodeType } from './types'

export function getNodeIcon(type: AggNodeType, size: number = 14): React.ReactNode {
  const p = { size, strokeWidth: 1.8 }
  switch (type) {
    case 'trace': return <Brain {...p} />
    case 'chain': return <GitBranch {...p} />
    case 'tool': return <Wrench {...p} />
    case 'llm': return <Bot {...p} />
    case 'parser': return <Link2 {...p} />
    default: return <Code {...p} />
  }
}

export function getNodeChipClasses(type: AggNodeType): string {
  switch (type) {
    case 'trace': return 'bg-slate-700  text-white'
    case 'chain': return 'bg-violet-500 text-white'
    case 'tool': return 'bg-emerald-500 text-white'
    case 'llm': return 'bg-rose-500   text-white'
    case 'parser': return 'bg-orange-400 text-white'
    default: return 'bg-slate-400  text-white'
  }
}

export function getBarColor(type: AggNodeType): string {
  switch (type) {
    case 'trace': return '#475569'
    case 'chain': return '#8b5cf6'
    case 'tool': return '#10b981'
    case 'llm': return '#f43f5e'
    case 'parser': return '#fb923c'
    default: return '#94a3b8'
  }
}

export function getNodeTypeLabel(type: AggNodeType): string {
  switch (type) {
    case 'trace': return 'Trace'
    case 'chain': return 'Chain'
    case 'tool': return 'Tool'
    case 'llm': return 'LLM'
    case 'parser': return 'Parser'
    default: return 'Node'
  }
}
