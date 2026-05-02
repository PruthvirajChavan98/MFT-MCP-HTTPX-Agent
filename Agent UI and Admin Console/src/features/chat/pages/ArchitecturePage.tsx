import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { motion } from 'motion/react'
import {
  ArrowLeft,
  CheckCircle2,
  Cog,
  Cookie,
  ExternalLink,
  Lock,
  ShieldAlert,
  ShieldCheck,
  TimerReset,
} from 'lucide-react'

import {
  CRMSwimlane,
  CodeBlock,
  COMPOSE_SERVICES,
  LangGraphDiagram,
  ObservabilityDiagram,
  SSEFrame,
  SectionHeader,
  SequenceDiagram,
  TOOL_COUNT,
  TOOLS,
  type TocEntry,
  TocRail,
  ToolTable,
  TopologyDiagram,
  WALKTHROUGH_A,
  WALKTHROUGH_B,
  WALKTHROUGH_C,
  Walkthrough,
} from './architecture'

const REPO_BLOB = 'https://github.com/PruthvirajChavan98/MFT-MCP-HTTPX-Agent/blob/main'

const TOC: readonly TocEntry[] = [
  { id: 'hero', index: '00', label: 'System overview' },
  { id: 'topology', index: '01', label: 'Topology' },
  { id: 'lifecycle', index: '02', label: 'Request lifecycle' },
  { id: 'inline-guard', index: '03', label: 'Inline guard' },
  { id: 'langgraph', index: '04', label: 'LangGraph supervisor' },
  { id: 'mcp', index: '05', label: 'MCP server' },
  { id: 'crm', index: '06', label: 'CRM bridge' },
  { id: 'frontend', index: '07', label: 'Frontend flow' },
  { id: 'walkthroughs', index: '08', label: 'Live walkthroughs' },
  { id: 'eval-store', index: '09', label: 'Eval store' },
  { id: 'security', index: '10', label: 'Security' },
  { id: 'observability', index: '11', label: 'Observability' },
  { id: 'deployment', index: '12', label: 'Deployment' },
  { id: 'principles', index: '13', label: 'Operating principles' },
] as const

export function ArchitecturePage() {
  return (
    <div className="min-h-screen bg-[#0a0d18] text-slate-300 selection:bg-cyan-500/30">
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            'linear-gradient(#22d3ee 1px, transparent 1px), linear-gradient(90deg, #22d3ee 1px, transparent 1px)',
          backgroundSize: '64px 64px',
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-x-0 top-0 h-[420px]"
        style={{
          background:
            'radial-gradient(ellipse 70% 50% at 50% 0%, rgba(34, 211, 238, 0.10), transparent 65%)',
        }}
      />

      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-[#0a0d18]/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-6">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-cyan-300"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Home
          </Link>
          <div className="flex items-center gap-3 font-mono text-[11px] tracking-[0.18em] text-slate-500">
            <span className="hidden sm:inline">MFT AGENT SERVICE</span>
            <span className="rounded-sm border border-cyan-500/30 bg-cyan-500/5 px-2 py-0.5 text-cyan-300">
              v1
            </span>
          </div>
        </div>
      </header>

      <main className="relative mx-auto max-w-[1280px] px-6 py-16 lg:grid lg:grid-cols-[1fr_220px] lg:gap-16">
        <article className="min-w-0 space-y-32">
          <Hero />
          <TopologySection />
          <LifecycleSection />
          <InlineGuardSection />
          <LangGraphSection />
          <McpSection />
          <CrmSection />
          <FrontendSection />
          <WalkthroughsSection />
          <EvalStoreSection />
          <SecuritySection />
          <ObservabilitySection />
          <DeploymentSection />
          <PrinciplesSection />
        </article>

        <aside className="lg:pt-16">
          <TocRail entries={TOC} />
        </aside>
      </main>

      <footer className="mt-32 border-t border-slate-800 bg-[#070912] py-10">
        <div className="mx-auto flex max-w-[1280px] flex-col items-start justify-between gap-4 px-6 md:flex-row md:items-center">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-md bg-cyan-400 text-xs font-bold text-[#0a0d18] shadow-[0_0_12px_rgba(34,211,238,0.4)]">
              MFT
            </span>
            <span className="font-semibold text-white">Mock FinTech</span>
          </div>
          <p className="text-[12px] font-mono tracking-wider text-slate-500">
            ARCHITECTURE DOCUMENTATION · MFT AGENT SERVICE
          </p>
        </div>
      </footer>
    </div>
  )
}

function Hero() {
  return (
    <section id="hero" className="scroll-mt-24">
      <div className="flex items-center gap-3 font-mono text-[11px] tracking-[0.22em] text-slate-500">
        <span className="rounded-sm border border-cyan-500/30 bg-cyan-500/5 px-2 py-0.5 text-cyan-300">
          00
        </span>
        <span>SYSTEM OVERVIEW</span>
      </div>
      <motion.h1
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="mt-6 max-w-4xl bg-gradient-to-r from-cyan-200 via-cyan-300 to-blue-400 bg-clip-text font-display text-5xl font-extrabold leading-[1.05] tracking-tight text-transparent md:text-6xl"
      >
        Architecture, end-to-end.
      </motion.h1>
      <motion.p
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.1 }}
        className="mt-6 max-w-3xl text-[17px] leading-relaxed text-slate-400"
      >
        Two FastAPI / FastMCP processes, a LangGraph supervisor with a Redis-backed checkpointer, a{' '}
        {TOOL_COUNT}-tool MCP server bridging an external CRM over HTTPS, all reverse-proxied
        through Nginx behind a Cloudflare tunnel. This page is the canonical answer to{' '}
        <em className="not-italic text-slate-200">how does this thing actually work</em> — every
        diagram and every claim is verifiable in the linked source.
      </motion.p>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.7, delay: 0.25 }}
        className="mt-10 grid grid-cols-1 gap-3 sm:grid-cols-3"
      >
        <Stat label="MCP tools" value={String(TOOL_COUNT)} sub="public + session-gated" />
        <Stat label="Processes" value="2" sub="agent · mcp" />
        <Stat label="Checkpointer TTL" value="7d" sub="AsyncRedisSaver" />
      </motion.div>
    </section>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-[#0c1322]/60 px-5 py-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className="mt-2 font-display text-3xl font-semibold text-white">{value}</p>
      <p className="mt-1 font-mono text-[11px] text-cyan-300/80">{sub}</p>
    </div>
  )
}

function TopologySection() {
  return (
    <Section
      id="topology"
      header={
        <SectionHeader
          index="01"
          eyebrow="TOPOLOGY"
          title="Eleven services in one compose stack"
          source={{ label: 'compose.yaml', href: `${REPO_BLOB}/compose.yaml` }}
        >
          The whole stack runs from a single <Mono>compose.yaml</Mono>. Cloudflare tunnel terminates
          the two public hostnames into the frontend container; from there everything is
          intra-network except the outbound CRM edge (dashed). Two backend planes, one shared data
          plane, dedicated workers, and a Prometheus / Grafana / Alertmanager observability arm.
        </SectionHeader>
      }
    >
      <TopologyDiagram />
      <details className="mt-6 rounded-xl border border-slate-800 bg-[#0c1322]/40">
        <summary className="cursor-pointer list-none px-5 py-3 font-mono text-[11px] uppercase tracking-[0.2em] text-slate-400 hover:text-cyan-300">
          <span className="mr-2 inline-block">›</span>
          Per-service breakdown ({COMPOSE_SERVICES.length} rows)
        </summary>
        <div className="overflow-x-auto border-t border-slate-800">
          <table className="w-full min-w-[760px] border-collapse text-left text-[12.5px]">
            <thead>
              <tr className="bg-slate-900/50 font-mono text-[10px] uppercase tracking-wider text-slate-500">
                <th className="px-4 py-2.5">Service</th>
                <th className="px-4 py-2.5">Image</th>
                <th className="px-4 py-2.5">Port</th>
                <th className="px-4 py-2.5">Network</th>
                <th className="px-4 py-2.5">Role</th>
              </tr>
            </thead>
            <tbody>
              {COMPOSE_SERVICES.map((svc) => (
                <tr key={svc.name} className="border-t border-slate-800/60">
                  <td className="px-4 py-2.5 font-mono text-cyan-300">{svc.name}</td>
                  <td className="px-4 py-2.5 font-mono text-[11.5px] text-slate-400">{svc.image}</td>
                  <td className="px-4 py-2.5 font-mono text-[11.5px] text-slate-300">{svc.port}</td>
                  <td className="px-4 py-2.5 font-mono text-[11.5px] text-indigo-300">{svc.network}</td>
                  <td className="px-4 py-2.5 text-slate-400">{svc.role}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Section>
  )
}

function LifecycleSection() {
  return (
    <Section
      id="lifecycle"
      header={
        <SectionHeader
          index="02"
          eyebrow="REQUEST LIFECYCLE"
          title="One prompt, seven lanes, six SSE frames"
          source={{
            label: 'agent_stream.py:414',
            href: `${REPO_BLOB}/backend/src/agent_service/api/endpoints/agent_stream.py#L414`,
          }}
        >
          The diagram traces the literal prompt{' '}
          <Mono>"I want to log in. My mobile is 9876543210."</Mono> from the browser's EventSource
          to the external CRM and back. Below it is the verbatim SSE transcript a prod stream
          returned for that prompt — the seam between &ldquo;agent thought&rdquo; and &ldquo;agent
          acted&rdquo; is the <Mono>tool_call</Mono> frame.
        </SectionHeader>
      }
    >
      <SequenceDiagram />
      <div className="mt-8">
        <SSEFrame
          caption="prod transcript · session 019de474-…"
          frames={WALKTHROUGH_A}
          highlightEvent="tool_call"
        />
      </div>
    </Section>
  )
}

function InlineGuardSection() {
  const blockedSnippet = `# backend/src/agent_service/api/endpoints/agent_stream.py:467
inline_guard_decision = await evaluate_prompt_safety_decision(request.question)

if not inline_guard_decision.allow and inline_guard_decision.decision == "block":
    async def blocked_event_generator():
        blocked_err = "Prompt violates security policy"
        ...
        yield sse_formatter.trace_event(collector.trace_id)
        yield {"event": "error",
               "data": json.dumps({"message": blocked_err})}
`
  return (
    <Section
      id="inline-guard"
      header={
        <SectionHeader
          index="03"
          eyebrow="INLINE GUARD"
          title="Why some prompts never reach the LLM"
          source={{
            label: 'agent_stream.py:467',
            href: `${REPO_BLOB}/backend/src/agent_service/api/endpoints/agent_stream.py#L467`,
          }}
        >
          The first thing the stream endpoint does — before any LLM call, before any tool — is run{' '}
          <Mono>evaluate_prompt_safety_decision()</Mono>. When it returns{' '}
          <Mono>decision="block"</Mono>, the stream emits exactly three frames and closes. From the
          browser this looks <em className="not-italic text-slate-200">indistinguishable</em> from
          a CRM reachability failure, but no CRM call is ever attempted. Outcomes: <Mono>pass</Mono>{' '}
          · <Mono>fail</Mono> · <Mono>degraded_allow</Mono> · <Mono>block</Mono>.
        </SectionHeader>
      }
    >
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-emerald-300">
            HAPPY PATH · pass
          </p>
          <SSEFrame caption="natural login phrasing" frames={WALKTHROUGH_A} highlightEvent="tool_call" />
        </div>
        <div>
          <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-rose-300">
            BLOCKED · decision=block
          </p>
          <SSEFrame caption="literal command-style prompt" frames={WALKTHROUGH_B} highlightEvent="error" />
        </div>
      </div>
      <div className="mt-8">
        <CodeBlock language="python" caption="blocked-path generator" code={blockedSnippet} />
      </div>
    </Section>
  )
}

function LangGraphSection() {
  const stateSnippet = `# backend/src/agent_service/core/recursive_rag_graph.py:22
class RecursiveRAGState(TypedDict):
    messages: Annotated[list, add_messages]
    iteration: int
    max_iterations: int
    tool_execution_cache: dict[str, str]
`
  return (
    <Section
      id="langgraph"
      header={
        <SectionHeader
          index="04"
          eyebrow="LANGGRAPH SUPERVISOR"
          title="A two-node loop with same-turn dedupe"
          source={{
            label: 'recursive_rag_graph.py',
            href: `${REPO_BLOB}/backend/src/agent_service/core/recursive_rag_graph.py`,
          }}
        >
          The supervisor is intentionally minimal: <Mono>llm_step</Mono> picks the next action,{' '}
          <Mono>run_tools</Mono> executes any tool calls via <Mono>DedupToolNode</Mono>, the loop
          re-enters until either the model emits no <Mono>tool_calls</Mono> or{' '}
          <Mono>iteration ≥ max_iterations</Mono>. Same-turn dedupe (by tool name + serialised args
          hash) is what stops the model from re-sending the same OTP twice in a single user turn.
        </SectionHeader>
      }
    >
      <LangGraphDiagram />
      <div className="mt-8">
        <CodeBlock language="python" caption="state shape" code={stateSnippet} />
      </div>
    </Section>
  )
}

function McpSection() {
  return (
    <Section
      id="mcp"
      header={
        <SectionHeader
          index="05"
          eyebrow="MCP SERVER"
          title={`The ${TOOL_COUNT}-tool catalogue`}
          source={{
            label: 'tool_descriptions.yaml',
            href: `${REPO_BLOB}/backend/src/mcp_service/tool_descriptions.yaml`,
          }}
        >
          The MCP server runs in its own process on port 8050 with its own Redis and HTTP clients.
          The agent reaches it over SSE transport via <Mono>tools.ainvoke()</Mono>. Two trust tiers:
          four tools are <Mono>PUBLIC</Mono> (no auth required); the rest require an{' '}
          <Mono>access_token</Mono> in the Redis session that <Mono>validate_otp</Mono> populates.
        </SectionHeader>
      }
    >
      <ToolTable />
      <div className="mt-8 grid gap-4 lg:grid-cols-2">
        <Callout
          title="The session_id magic"
          icon={<Cog className="h-4 w-4 text-cyan-300" />}
          source={{
            label: 'mcp_manager.py:87',
            href: `${REPO_BLOB}/backend/src/agent_service/tools/mcp_manager.py#L87`,
          }}
        >
          <p>
            Pydantic <Mono>create_model()</Mono> strips <Mono>session_id</Mono> from the schema the
            LLM ever sees. The wrapper at line 134 then injects it back before invoking the remote
            tool. That is why the LLM never has to know the session id — and why one session's
            tool calls cannot be hijacked by another.
          </p>
        </Callout>
        <Callout
          title="PUBLIC_TOOLS whitelist"
          icon={<ShieldCheck className="h-4 w-4 text-emerald-300" />}
          source={{
            label: 'mcp_manager.py:19',
            href: `${REPO_BLOB}/backend/src/agent_service/tools/mcp_manager.py#L19`,
          }}
        >
          <p>
            Exactly four tools live outside the auth gate:{' '}
            {TOOLS.filter((t) => t.tier === 'public').map((t, i, arr) => (
              <span key={t.name}>
                <Mono>{t.name}</Mono>
                {i < arr.length - 1 ? ', ' : '.'}
              </span>
            ))}{' '}
            Everything else is filtered out by <Mono>rebuild_tools_for_user()</Mono> when the
            session has no <Mono>access_token</Mono>.
          </p>
        </Callout>
      </div>
    </Section>
  )
}

function CrmSection() {
  const httpxSnippet = `# backend/src/mcp_service/auth_api.py:74
TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0)
LIMITS  = httpx.Limits(max_connections=20, max_keepalive_connections=10)
`
  return (
    <Section
      id="crm"
      header={
        <SectionHeader
          index="06"
          eyebrow="CRM BRIDGE"
          title="Outbound HTTPS, two auth schemes"
          source={{
            label: 'auth_api.py · core_api.py',
            href: `${REPO_BLOB}/backend/src/mcp_service/auth_api.py`,
          }}
        >
          The CRM is <em className="not-italic text-slate-200">external</em> to this stack — there
          is no <Mono>crm_api</Mono> service in <Mono>compose.yaml</Mono>. MCP calls{' '}
          <Mono>https://test-mock-crm.pruthvirajchavan.codes</Mono> directly via{' '}
          <Mono>httpx.AsyncClient</Mono>. Public tools authenticate with HTTP Basic; session-gated
          tools attach a Bearer token obtained at <Mono>validate_otp</Mono>.
        </SectionHeader>
      }
    >
      <CRMSwimlane />
      <div className="mt-8">
        <CodeBlock language="python" caption="httpx profile" code={httpxSnippet} />
      </div>
      <ul className="mt-6 grid gap-3 text-[14px] leading-relaxed text-slate-300 sm:grid-cols-3">
        <li className="rounded-md border border-slate-800 bg-[#0c1322]/40 p-4">
          <p className="font-mono text-[10px] uppercase tracking-wider text-cyan-300">EXTERNAL</p>
          <p className="mt-2">No <Mono>crm_api</Mono> container exists in this project's compose.</p>
        </li>
        <li className="rounded-md border border-slate-800 bg-[#0c1322]/40 p-4">
          <p className="font-mono text-[10px] uppercase tracking-wider text-cyan-300">FAIL-FAST</p>
          <p className="mt-2">
            MCP refuses to start without <Mono>BASIC_AUTH_USERNAME</Mono> and{' '}
            <Mono>BASIC_AUTH_PASSWORD</Mono>.
          </p>
        </li>
        <li className="rounded-md border border-slate-800 bg-[#0c1322]/40 p-4">
          <p className="font-mono text-[10px] uppercase tracking-wider text-cyan-300">TWO TIERS</p>
          <p className="mt-2">
            Basic auth for OTP send/validate; Bearer token for everything else.
          </p>
        </li>
      </ul>
    </Section>
  )
}

function FrontendSection() {
  return (
    <Section
      id="frontend"
      header={
        <SectionHeader
          index="07"
          eyebrow="FRONTEND FLOW"
          title="React 19 + Vite 8 + a server-first chat hydration rule"
          source={{
            label: 'src/app/routes.ts',
            href: `${REPO_BLOB}/Agent UI and Admin Console/src/app/routes.ts`,
          }}
        >
          The UI is feature-sliced. Lazy routes for landing, this architecture page, and the admin
          console. The chat widget hydrates from the LangGraph checkpointer first; localStorage is
          only a write-through cache. Reversing that order silently shows stale messages.
        </SectionHeader>
      }
    >
      <div className="grid gap-6 lg:grid-cols-2">
        <Callout title="Routing" icon={<ExternalLink className="h-4 w-4 text-cyan-300" />}>
          <ul className="space-y-1.5 font-mono text-[12.5px]">
            <li>
              <Mono>/</Mono> · <span className="text-slate-400">NBFCLandingPage</span>
            </li>
            <li>
              <Mono>/architecture</Mono> · <span className="text-slate-400">this page</span>
            </li>
            <li>
              <Mono>/admin/login</Mono> · <span className="text-slate-400">JWT auth</span>
            </li>
            <li>
              <Mono>/admin/&lt;sub&gt;</Mono> ·{' '}
              <span className="text-slate-400">trace viewer, KB, costs, model config…</span>
            </li>
          </ul>
        </Callout>
        <Callout title="Chat hydration order" icon={<TimerReset className="h-4 w-4 text-cyan-300" />}>
          <ol className="list-inside list-decimal space-y-1.5 text-[13.5px]">
            <li>Read <Mono>SESSION_KEY</Mono> from localStorage if present.</li>
            <li>
              Fetch from server checkpointer via <Mono>fetchSessionMessages(sid)</Mono>.{' '}
              <span className="text-slate-500">— authoritative</span>
            </li>
            <li>Fall back to localStorage cache if the server fetch fails.</li>
            <li>Write-through to <Mono>messageKey(sid)</Mono> after each render.</li>
          </ol>
          <p className="mt-3 text-[12px] text-slate-500">
            Never reverse this order; <Mono>CLAUDE.md:208</Mono> codifies it.
          </p>
        </Callout>
        <Callout title="HTTP layer" icon={<Cookie className="h-4 w-4 text-cyan-300" />}>
          <p>
            Centralised in <Mono>src/shared/api/http.ts</Mono>. RFC 7807 <Mono>Problem</Mono>-shape
            parsing, CSRF double-submit via <Mono>X-CSRF-Token</Mono>. Two custom DOM events fire
            on auth failure:
          </p>
          <ul className="mt-2 space-y-1 font-mono text-[12px]">
            <li>
              <span className="text-amber-300">401 →</span> <Mono>ADMIN_SESSION_EXPIRED_EVENT</Mono>
            </li>
            <li>
              <span className="text-amber-300">403 / mfa_required →</span>{' '}
              <Mono>ADMIN_MFA_REQUIRED_EVENT</Mono>
            </li>
          </ul>
        </Callout>
        <Callout title="MFA prompt" icon={<Lock className="h-4 w-4 text-cyan-300" />}>
          <p>
            Super-admin mutations chain through <Mono>require_mfa_fresh</Mono>. The frontend wraps
            every such call with <Mono>withMfa(label, fn)</Mono>: 403/<Mono>mfa_required</Mono>{' '}
            opens the modal, the user submits their TOTP, the original mutation retries once.
          </p>
          <p className="mt-3 text-[12px] text-slate-500">
            Skipping <Mono>withMfa()</Mono> for any new mutation is a hard rule violation —{' '}
            <Mono>CLAUDE.md:206</Mono>.
          </p>
        </Callout>
      </div>
    </Section>
  )
}

function WalkthroughsSection() {
  return (
    <Section
      id="walkthroughs"
      header={
        <SectionHeader
          index="08"
          eyebrow="LIVE WALKTHROUGHS"
          title="Three sessions, three outcomes"
        >
          Real captured SSE transcripts (the third is representative — bearer tokens are not safe
          to surface verbatim). Read top-to-bottom; the diagnostic frame is annotated.
        </SectionHeader>
      }
    >
      <div className="space-y-8">
        <Walkthrough
          index="A"
          title="Public path · OTP send"
          prompt="I want to log in. My mobile is 9876543210."
          sessionId="019de474-35f2-7ac2-aabb-684816321519"
          frames={WALKTHROUGH_A}
          highlightEvent="tool_call"
          outcome={
            <>
              The agent picks <Mono>generate_otp</Mono>; MCP forwards Basic-Auth POST to{' '}
              <Mono>/mockfin-service/otp/generate_new/</Mono>; CRM responds{' '}
              <Mono>OTP Sent, 9876543210, OTP generated Successfully</Mono>. The user receives the
              OTP on WhatsApp. CRM is reachable end-to-end.
            </>
          }
        />
        <Walkthrough
          index="B"
          title="Inline-guard block · looks like CRM, isn't"
          prompt="Generate an OTP for mobile 9876543210."
          sessionId="019de473-e657-7053-8b27-6b92d8fd3903"
          frames={WALKTHROUGH_B}
          highlightEvent="error"
          variant="block"
          outcome={
            <>
              Three frames total. The inline guard returned <Mono>decision=block</Mono>; no LLM
              call, no tool, no CRM hit. From the browser this is indistinguishable from a CRM
              outage — but the diagnostic frame is the <Mono>error</Mono> event, not a missing{' '}
              <Mono>tool_call</Mono>.
            </>
          }
        />
        <Walkthrough
          index="C"
          title="Session-gated path · loan dashboard"
          prompt="Show me my loan dashboard."
          sessionId="019de4a1-c7b8-…  (representative)"
          frames={WALKTHROUGH_C}
          highlightEvent="tool_call"
          outcome={
            <>
              The session already carries a Bearer token from <Mono>validate_otp</Mono>. The agent
              picks <Mono>dashboard_home</Mono>; MCP attaches the bearer and calls{' '}
              <Mono>GET /mockfin-service/home</Mono>. Result is folded back as a{' '}
              <Mono>tool_call</Mono> frame, then the model paraphrases for the user.
            </>
          }
        />
      </div>
    </Section>
  )
}

function EvalStoreSection() {
  return (
    <Section
      id="eval-store"
      header={
        <SectionHeader
          index="09"
          eyebrow="EVAL STORE"
          title="Embed-on-commit, defensive vector search, two operational scripts"
          source={{
            label: 'eval_store/',
            href: `${REPO_BLOB}/backend/src/agent_service/eval_store`,
          }}
        >
          Every persisted trace fires <Mono>embed_trace_if_needed()</Mono> via the fire-and-forget
          helper in <Mono>eval_store/_bg.py</Mono>. A strong-ref set prevents{' '}
          <Mono>asyncio.create_task()</Mono> handles from being garbage-collected mid-flight.
        </SectionHeader>
      }
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <Callout title="Recent ops" icon={<CheckCircle2 className="h-4 w-4 text-emerald-300" />}>
          <ul className="space-y-2 text-[13.5px]">
            <li>
              <Mono>9215882</Mono>{' '}
              <span className="text-slate-400">PR #7</span> — unconditional embed on every trace
              commit; same-text re-submit fix in admin semantic search.
            </li>
            <li>
              <Mono>34056fc</Mono>{' '}
              <span className="text-slate-400">PR #6</span> — rebuild{' '}
              <Mono>eval_results_emb</Mono> Milvus collection; defensive id resolution in{' '}
              <Mono>eval_vector_search</Mono> (trace_id → pk → doc.id).
            </li>
          </ul>
        </Callout>
        <Callout title="Operator scripts" icon={<Cog className="h-4 w-4 text-cyan-300" />}>
          <CodeBlock
            language="bash"
            caption="run once per environment"
            code={`make -C backend rebuild-eval-results-collection
make -C backend backfill-trace-embeddings`}
          />
        </Callout>
      </div>
      <div className="mt-6 rounded-xl border border-slate-800 bg-[#0c1322]/40 p-5 text-[13.5px] text-slate-300">
        <p className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
          MILVUS COLLECTIONS
        </p>
        <ul className="mt-3 space-y-1.5 font-mono">
          <li>
            <span className="text-cyan-300">kb_faqs</span>{' '}
            <span className="text-slate-500">— FAQ knowledge base, 1536-dim</span>
          </li>
          <li>
            <span className="text-cyan-300">eval_traces_emb</span>{' '}
            <span className="text-slate-500">— trace text → admin semantic search</span>
          </li>
          <li>
            <span className="text-cyan-300">eval_results_emb</span>{' '}
            <span className="text-slate-500">— shadow-judge eval results, mirrors PG</span>
          </li>
        </ul>
      </div>
    </Section>
  )
}

function SecuritySection() {
  const items = [
    {
      icon: <ShieldAlert className="h-4 w-4 text-rose-300" />,
      title: 'Inline input guard',
      body: 'evaluate_prompt_safety_decision() runs before the LLM. Blocks emit error + done only.',
    },
    {
      icon: <ShieldCheck className="h-4 w-4 text-cyan-300" />,
      title: 'Rate limit · fail-closed',
      body: 'RATE_LIMIT_FAILURE_MODE defaults to fail_closed; LLM budget is protected on Redis outage.',
    },
    {
      icon: <Lock className="h-4 w-4 text-cyan-300" />,
      title: 'Admin auth + 5-min MFA freshness',
      body: 'JWT cookie bound to admin_users.id; super-admin mutations gated by require_mfa_fresh.',
    },
    {
      icon: <ShieldCheck className="h-4 w-4 text-emerald-300" />,
      title: 'Argon2id password hashes',
      body: 'Compose env-file gotcha — every $ doubled to $$ in .env, else login returns invalid_credentials.',
    },
    {
      icon: <ShieldAlert className="h-4 w-4 text-rose-300" />,
      title: 'Tor exit-node block',
      body: 'geoip_updater container refreshes the list daily; nginx denies on match.',
    },
    {
      icon: <ShieldCheck className="h-4 w-4 text-cyan-300" />,
      title: 'Nginx L7 DoS defense',
      body: 'limit_req_zone + limit_conn_zone with NAT-safe thresholds; runtime DNS via $agent_upstream.',
    },
  ]
  return (
    <Section
      id="security"
      header={
        <SectionHeader index="10" eyebrow="SECURITY" title="Six layers, each with a single source-of-truth">
          Defence in depth — the inline guard catches prompt-injection before the LLM, the rate
          limiter caps cost, MFA freshness gates super-admin mutations, and the edge nginx config
          handles L7 noise so FastAPI does not have to.
        </SectionHeader>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((item) => (
          <div
            key={item.title}
            className="flex gap-3 rounded-md border border-slate-800 bg-[#0c1322]/40 p-4"
          >
            <div className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-md border border-slate-800 bg-slate-950/60">
              {item.icon}
            </div>
            <div>
              <p className="font-display text-[14px] font-semibold text-slate-100">{item.title}</p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-slate-400">{item.body}</p>
            </div>
          </div>
        ))}
      </div>
    </Section>
  )
}

function ObservabilitySection() {
  return (
    <Section
      id="observability"
      header={
        <SectionHeader index="11" eyebrow="OBSERVABILITY" title="Prometheus scrape · Grafana · Alertmanager">
          The agent exposes <Mono>/metrics</Mono>. Prometheus scrapes on its default loop, Grafana
          renders the dashboards, Alertmanager fans out routing rules. All three run in the same
          compose stack.
        </SectionHeader>
      }
    >
      <ObservabilityDiagram />
    </Section>
  )
}

function DeploymentSection() {
  const deploySnippet = `# from repo root
make deploy-prod        # rebuild agent + mcp images, force-recreate

# nginx survives container recreates because it resolves the upstream
# at request time:
#   resolver 127.0.0.11 valid=10s;       (Docker embedded resolver)
#   set $agent_upstream agent;
#   proxy_pass http://$agent_upstream:8000;
`
  return (
    <Section
      id="deployment"
      header={
        <SectionHeader
          index="12"
          eyebrow="DEPLOYMENT"
          title="One make target, runtime-DNS proxy, two tunnel hostnames"
          source={{
            label: 'nginx.conf:13',
            href: `${REPO_BLOB}/Agent UI and Admin Console/nginx.conf#L13`,
          }}
        >
          <Mono>make deploy-prod</Mono> rebuilds the <Mono>agent</Mono> and <Mono>mcp</Mono> images
          and force-recreates them. Nginx uses Docker's embedded resolver at{' '}
          <Mono>127.0.0.11</Mono> with a 10-second TTL, so a container recreate doesn't strand
          stale upstream IPs (PR #20). Cloudflare tunnel routes{' '}
          <Mono>mft-agent.pruthvirajchavan.codes</Mono> and{' '}
          <Mono>mft-api.pruthvirajchavan.codes</Mono>.
        </SectionHeader>
      }
    >
      <CodeBlock language="bash" caption="prod deploy + the resolver fix" code={deploySnippet} />
    </Section>
  )
}

function PrinciplesSection() {
  const principles = [
    {
      title: 'No patchwork',
      body: 'Only permanent, enterprise-grade solutions. Temporary fixes are rejected on sight.',
    },
    {
      title: 'Research-backed',
      body: 'Dependency picks and migrations verified against the package registry + official changelog. Training data is not a source.',
    },
    {
      title: 'Zero deprecation warnings',
      body: 'make test-deprecation and npm run verify:deprecation are gates, not advisory.',
    },
    {
      title: 'End-to-end ownership',
      body: 'If a task surfaces adjacent broken behaviour, fix the root cause. Do not leave a trap.',
    },
  ]
  return (
    <Section
      id="principles"
      header={
        <SectionHeader
          index="13"
          eyebrow="OPERATING PRINCIPLES"
          title="The rules this codebase enforces"
          source={{ label: 'CLAUDE.md', href: `${REPO_BLOB}/CLAUDE.md` }}
        />
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {principles.map((p) => (
          <div
            key={p.title}
            className="rounded-xl border border-slate-800 bg-[#0c1322]/50 p-5 transition-colors hover:border-cyan-500/30"
          >
            <p className="font-display text-[15px] font-semibold text-white">{p.title}</p>
            <p className="mt-2 text-[13px] leading-relaxed text-slate-400">{p.body}</p>
          </div>
        ))}
      </div>
    </Section>
  )
}

function Section({
  id,
  header,
  children,
}: {
  id: string
  header: ReactNode
  children: ReactNode
}) {
  return (
    <motion.section
      id={id}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
      className="scroll-mt-24"
    >
      {header}
      {children}
    </motion.section>
  )
}

function Callout({
  title,
  icon,
  source,
  children,
}: {
  title: string
  icon: ReactNode
  source?: { label: string; href: string }
  children: ReactNode
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-[#0c1322]/50 p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="grid h-7 w-7 place-items-center rounded-md border border-slate-800 bg-slate-950/60">
            {icon}
          </div>
          <h3 className="font-display text-[14.5px] font-semibold text-slate-100">{title}</h3>
        </div>
        {source && (
          <a
            href={source.href}
            target="_blank"
            rel="noreferrer"
            className="font-mono text-[10px] tracking-wider text-slate-500 transition-colors hover:text-cyan-300"
          >
            {source.label} ↗
          </a>
        )}
      </div>
      <div className="space-y-2 text-[13.5px] leading-relaxed text-slate-400">{children}</div>
    </div>
  )
}

function Mono({ children }: { children: ReactNode }) {
  return (
    <code className="rounded bg-slate-900/70 px-1.5 py-0.5 font-mono text-[12px] text-cyan-300">
      {children}
    </code>
  )
}
