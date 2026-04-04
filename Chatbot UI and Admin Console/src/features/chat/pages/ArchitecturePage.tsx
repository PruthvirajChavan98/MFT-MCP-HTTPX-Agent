import type { ReactNode, ElementType } from 'react'
import { Link } from 'react-router'
import { motion } from 'motion/react'
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  Boxes,
  CircleCheckBig,
  Cpu,
  Database,
  GitBranch,
  MessageSquareText,
  Network,
  Server,
  Shield,
  TerminalSquare,
  Workflow,
  Wrench,
  Zap,
} from 'lucide-react'

// ─── Sub-components ─────────────────────────────────────────────────────────

const BADGE_COLORS = {
  cyan: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  slate: 'bg-slate-800 text-slate-300 border-slate-700',
  indigo: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
  emerald: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
} as const

type BadgeColor = keyof typeof BADGE_COLORS

function Badge({ children, color = 'cyan' }: { children: ReactNode; color?: BadgeColor }) {
  return (
    <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${BADGE_COLORS[color]}`}>
      {children}
    </span>
  )
}

function Card({
  title,
  icon: Icon,
  children,
  delay = 0,
}: {
  title: string
  icon: ElementType
  children: ReactNode
  delay?: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className="group rounded-2xl border border-slate-800 bg-[#111827]/80 p-6 shadow-lg shadow-black/20 backdrop-blur-xl transition-all duration-300 hover:border-cyan-500/30"
    >
      <div className="mb-6 flex items-center gap-3">
        <div className="rounded-xl bg-cyan-500/10 p-2.5 transition-colors group-hover:bg-cyan-500/20">
          <Icon className="h-5 w-5 text-cyan-400" />
        </div>
        <h3 className="text-xl font-semibold tracking-tight text-white">{title}</h3>
      </div>
      <div className="space-y-3">{children}</div>
    </motion.div>
  )
}

function ListItem({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-3 text-sm leading-relaxed text-slate-300">
      <div className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(6,182,212,0.6)]" />
      <p>{children}</p>
    </div>
  )
}

const DIAGRAM_NODE_BORDER = {
  cyan: 'border-cyan-500/30 shadow-[0_0_15px_rgba(6,182,212,0.1)]',
  indigo: 'border-indigo-500/30 shadow-[0_0_15px_rgba(99,102,241,0.1)]',
  emerald: 'border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.1)]',
  slate: 'border-slate-700 shadow-none',
} as const

const DIAGRAM_NODE_ICON = {
  cyan: 'text-cyan-400',
  indigo: 'text-indigo-400',
  emerald: 'text-emerald-400',
  slate: 'text-slate-400',
} as const

type DiagramColor = keyof typeof DIAGRAM_NODE_BORDER

function DiagramNode({
  icon: Icon,
  label,
  subtext,
  color = 'cyan',
}: {
  icon: ElementType
  label: string
  subtext?: string
  color?: DiagramColor
}) {
  return (
    <div
      className={`relative z-10 flex min-w-[130px] flex-col items-center justify-center rounded-2xl border bg-slate-900/80 p-4 ${DIAGRAM_NODE_BORDER[color]}`}
    >
      <Icon className={`mb-2 h-7 w-7 ${DIAGRAM_NODE_ICON[color]}`} />
      <span className="text-center text-sm font-semibold text-white">{label}</span>
      {subtext && <span className="mt-1 text-xs text-slate-500">{subtext}</span>}
    </div>
  )
}

function FlowArrow() {
  return (
    <div className="flex shrink-0 justify-center py-3 text-cyan-500/30 lg:px-2 lg:py-0">
      <ArrowRight className="h-5 w-5 rotate-90 lg:rotate-0" />
    </div>
  )
}

// ─── Main component ─────────────────────────────────────────────────────────

export function ArchitecturePage() {
  return (
    <div className="min-h-screen bg-[#0B1121] pb-20 font-sans text-slate-300 selection:bg-cyan-500/30">
      {/* Background grid */}
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.03]"
        style={{
          backgroundImage: 'radial-gradient(#06b6d4 1px, transparent 1px)',
          backgroundSize: '32px 32px',
        }}
      />

      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-[#0B1121]/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <Link
            to="/"
            className="flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-cyan-400"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Home</span>
          </Link>
          <div className="text-sm font-medium tracking-wide text-slate-300">MFT Agent Service</div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 pt-20">
        {/* Hero */}
        <div className="mx-auto mb-24 max-w-3xl text-center">
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="mb-6 bg-gradient-to-r from-teal-400 via-cyan-400 to-blue-500 bg-clip-text text-5xl font-extrabold tracking-tight text-transparent md:text-6xl"
          >
            System Architecture
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-lg leading-relaxed text-slate-400"
          >
            A production-grade conversational AI stack built on FastAPI, LangGraph, and the Model
            Context Protocol — from request ingress to tool execution.
          </motion.p>
        </div>

        {/* ── Flow diagram ── */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="relative mb-8"
        >
          <div className="-z-10 absolute inset-0 rounded-3xl bg-gradient-to-b from-cyan-500/5 to-transparent blur-3xl" />

          <div className="overflow-x-auto rounded-3xl border border-slate-800 bg-[#111827]/50 p-8 shadow-2xl backdrop-blur-xl lg:p-12">
            <div className="mb-10 flex items-center gap-3">
              <div className="rounded-xl bg-cyan-500/10 p-2.5">
                <Network className="h-6 w-6 text-cyan-400" />
              </div>
              <h2 className="text-2xl font-semibold text-white">End-to-End Request Flow</h2>
            </div>

            {/* Pipeline: 7 nodes */}
            <div className="flex w-full flex-col items-center justify-center py-8">
              <div className="flex w-full flex-col items-center justify-center gap-0 lg:flex-row lg:flex-wrap lg:justify-center lg:gap-0">
                <DiagramNode icon={MessageSquareText} label="NL Query" subtext="User Input" color="cyan" />
                <FlowArrow />
                <DiagramNode icon={Shield} label="Nginx" subtext="Ingress" color="indigo" />
                <FlowArrow />
                <DiagramNode icon={Server} label="FastAPI" subtext="API Gateway" color="cyan" />
                <FlowArrow />
                <DiagramNode icon={Workflow} label="LangGraph" subtext="Agent Engine" color="cyan" />
                <FlowArrow />
                <DiagramNode icon={Cpu} label="MCP Server" subtext="Protocol" color="emerald" />
                <FlowArrow />
                <DiagramNode icon={Wrench} label="Tools" subtext="Execution" color="emerald" />
                <FlowArrow />
                <DiagramNode icon={CircleCheckBig} label="Resolution" subtext="Response" color="cyan" />
              </div>
            </div>

            {/* Tech badges */}
            <div className="mt-6 flex flex-wrap justify-center gap-2 border-t border-slate-800 pt-8">
              <Badge color="emerald">Python 3.11</Badge>
              <Badge color="cyan">FastAPI</Badge>
              <Badge color="cyan">LangGraph</Badge>
              <Badge color="cyan">LangChain</Badge>
              <Badge color="indigo">Milvus</Badge>
              <Badge color="indigo">PostgreSQL</Badge>
              <Badge color="emerald">Redis</Badge>
              <Badge color="indigo">Docker</Badge>
              <Badge color="indigo">Nginx</Badge>
              <Badge color="emerald">Memgraph</Badge>
            </div>
          </div>
        </motion.div>

        {/* ── Data layer (separate pane) ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.35 }}
          className="mb-24 rounded-3xl border border-slate-800 bg-[#111827]/50 p-8 shadow-2xl backdrop-blur-xl lg:p-12"
        >
          <div className="mb-8 flex items-center gap-3">
            <div className="rounded-xl bg-indigo-500/10 p-2.5">
              <Database className="h-6 w-6 text-indigo-400" />
            </div>
            <h2 className="text-2xl font-semibold text-white">Data Layer</h2>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-6">
            <DiagramNode icon={Database} label="PostgreSQL" subtext="State & Traces" color="indigo" />
            <DiagramNode icon={Boxes} label="Milvus" subtext="Vector DB" color="indigo" />
            <DiagramNode icon={Zap} label="Redis" subtext="Cache / State" color="emerald" />
            <DiagramNode icon={GitBranch} label="Memgraph" subtext="Graph DB" color="emerald" />
          </div>
        </motion.div>

        {/* Section cards */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:gap-8">
          <Card title="Model Context Protocol" icon={Cpu} delay={0.3}>
            <ListItem>FastMCP server on SSE transport (port 8050)</ListItem>
            <ListItem>
              12 tools: generate_otp, validate_otp, is_logged_in, logout, list_loans, select_loan,
              dashboard_home, loan_details...
            </ListItem>
            <ListItem>Session-scoped tool injection (public vs authenticated)</ListItem>
            <ListItem>Side-effect execution policy with same-turn dedupe</ListItem>
          </Card>

          <Card title="LangGraph Agent" icon={Workflow} delay={0.4}>
            <ListItem>
              Recursive RAG graph: llm_step &rarr; run_tools &rarr; llm_step (loop)
            </ListItem>
            <ListItem>Max 6 iterations per turn</ListItem>
            <ListItem>Tool execution cache for side-effect dedupe</ListItem>
            <ListItem>Asyncpg checkpointer (PostgreSQL)</ListItem>
          </Card>

          <Card title="Knowledge Base" icon={Database} delay={0.5}>
            <ListItem>Milvus vector store for semantic FAQ search</ListItem>
            <ListItem>PostgreSQL persistence with vector sync tracking</ListItem>
            <ListItem>PDF ingest pipeline for document upload</ListItem>
            <ListItem>Cosine similarity scoring with threshold filtering</ListItem>
          </Card>

          <Card title="Real-time Streaming" icon={Activity} delay={0.6}>
            <ListItem>LangGraph astream_events v2 pipeline</ListItem>
            <ListItem>
              SSE event types: token, reasoning, tool_call, cost, follow_ups, trace, done
            </ListItem>
            <ListItem>Nested Runnable dedup via parent_ids filtering</ListItem>
            <ListItem>Inline follow-up extraction from LLM output</ListItem>
          </Card>

          <Card title="Infrastructure" icon={Server} delay={0.7}>
            <ListItem>10+ Docker Compose services</ListItem>
            <ListItem>
              Services: agent, mcp, router_worker, shadow_judge_worker, frontend, cloudflared
            </ListItem>
            <ListItem>Monitoring: Prometheus, Grafana, Alertmanager</ListItem>
            <ListItem>PostgreSQL (pool: 10-50), Redis, Milvus, Memgraph</ListItem>
          </Card>

          <Card title="Security Layers" icon={Shield} delay={0.8}>
            <ListItem>OTP authentication via WhatsApp</ListItem>
            <ListItem>Tor exit node blocking with real-time list refresh</ListItem>
            <ListItem>
              Session risk scoring (impossible travel, concurrent IPs, device mismatch)
            </ListItem>
            <ListItem>Inline prompt injection guardrails (gpt-oss-safeguard-20b)</ListItem>
            <ListItem>Per-endpoint rate limiting (sliding window + token bucket)</ListItem>
          </Card>

          <Card title="Observability" icon={TerminalSquare} delay={0.9}>
            <ListItem>Runtime trace collection with PostgreSQL persistence</ListItem>
            <ListItem>Shadow evaluation pipeline (10% sample rate)</ListItem>
            <ListItem>
              Admin analytics dashboard (conversations, costs, guardrails, users)
            </ListItem>
            <ListItem>Live SSE dashboards for real-time monitoring</ListItem>
            <ListItem>Prometheus metrics with Grafana visualization</ListItem>
          </Card>
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-32 border-t border-slate-800 bg-[#070A12] py-8">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between px-6 md:flex-row">
          <div className="mb-4 flex items-center gap-3 md:mb-0">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500 text-xs font-bold text-[#0B1121] shadow-[0_0_12px_rgba(6,182,212,0.4)]">
              MFT
            </div>
            <span className="font-semibold text-white">Mock FinTech</span>
          </div>
          <p className="text-sm text-slate-500">Architecture documentation -- MFT Agent Service</p>
        </div>
      </footer>
    </div>
  )
}
