import { DiagramFallback } from './DiagramFallback'

/**
 * Vertical sequence diagram for the canonical request:
 *   "I want to log in. My mobile is 9876543210."
 *
 * Lanes left → right: Browser, Nginx, Agent, Inline-Guard, LangGraph,
 * MCP server, CRM. Time flows top → bottom. Real file:line callouts on
 * every arrow.
 */
export function SequenceDiagram() {
  const lanes = [
    { x: 80, label: 'Browser', sub: 'EventSource' },
    { x: 240, label: 'Nginx', sub: '/api/agent/stream' },
    { x: 400, label: 'Agent', sub: 'FastAPI :8000' },
    { x: 540, label: 'Guard', sub: 'inline_guard.py' },
    { x: 680, label: 'LangGraph', sub: 'recursive_rag_graph' },
    { x: 820, label: 'MCP', sub: 'FastMCP :8050' },
    { x: 960, label: 'CRM', sub: 'test-mock-crm.*' },
  ] as const

  const TOP = 90
  const BOTTOM = 1140

  const arrows = [
    { from: 0, to: 1, y: 130, label: 'POST /api/agent/stream', sub: 'EventSource open' },
    { from: 1, to: 2, y: 175, label: 'proxy_pass $agent_upstream', sub: 'nginx.conf:50' },
    { from: 2, to: 3, y: 240, label: 'evaluate_prompt_safety_decision()', sub: 'agent_stream.py:467' },
    { from: 3, to: 2, y: 280, label: 'decision="pass"', sub: '— continue' },
    { from: 2, to: 0, y: 320, label: 'event: trace', sub: '{"trace_id":"…"}', tone: 'cyan' },
    { from: 2, to: 4, y: 380, label: 'graph.astream_events(version="v2")', sub: 'app_factory.py:77 (AsyncRedisSaver)' },
    { from: 4, to: 0, y: 430, label: 'event: reasoning', sub: '"User wants to log in…"', tone: 'indigo' },
    { from: 4, to: 5, y: 510, label: 'tool_wrapper(generate_otp, sid)', sub: 'mcp_manager.py:134', tone: 'emerald' },
    { from: 5, to: 6, y: 580, label: 'POST /mockfin-service/otp/generate_new/', sub: 'auth_api.py:101  Basic crm:crm', tone: 'cyan-dashed' },
    { from: 6, to: 5, y: 660, label: 'CSV: OTP Sent,9876543210,…', sub: 'httpx 200 OK', tone: 'cyan-dashed' },
    { from: 5, to: 4, y: 720, label: '_touch(sid, "generate_otp")', sub: 'server.py:65', tone: 'emerald' },
    { from: 4, to: 0, y: 780, label: 'event: tool_call', sub: '{"name":"generate_otp", "output":"…"}', tone: 'emerald' },
    { from: 4, to: 0, y: 840, label: 'event: token  × N', sub: 'streamed answer chunks', tone: 'slate' },
    { from: 4, to: 0, y: 900, label: 'event: cost', sub: '{"total":0.000174,"model":"openai/gpt-oss-120b"}', tone: 'amber' },
    { from: 4, to: 2, y: 960, label: 'graph turn complete', sub: 'iteration ≤ max_iterations' },
    { from: 2, to: 0, y: 1000, label: 'event: done', sub: '{"status":"complete"}', tone: 'cyan' },
  ] as const

  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0c1322]/60 p-2 shadow-2xl shadow-black/40 backdrop-blur">
      <div className="overflow-x-auto">
        <svg
          viewBox="0 0 1100 1180"
          role="img"
          aria-labelledby="seq-title seq-desc"
          xmlns="http://www.w3.org/2000/svg"
          className="block h-auto w-full min-w-[860px]"
        >
          <title id="seq-title">Request lifecycle for the OTP login prompt</title>
          <desc id="seq-desc">
            The browser opens an EventSource against /api/agent/stream. Nginx forwards to the agent.
            The inline guard at agent_stream.py:467 evaluates the prompt and passes it through. The
            LangGraph supervisor selects generate_otp; the MCP server executes the tool, which calls
            the external CRM via outbound HTTPS Basic auth. The agent emits trace, reasoning,
            tool_call, token chunks, cost, and done SSE frames in that order.
          </desc>

          <defs>
            <marker id="seq-arrow-cyan" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#22d3ee" />
            </marker>
            <marker id="seq-arrow-indigo" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#818cf8" />
            </marker>
            <marker id="seq-arrow-emerald" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#34d399" />
            </marker>
            <marker id="seq-arrow-slate" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#64748b" />
            </marker>
            <marker id="seq-arrow-amber" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#fbbf24" />
            </marker>
          </defs>

          {/* Lane heads + lifelines */}
          {lanes.map((lane) => (
            <g key={lane.label}>
              <rect x={lane.x - 50} y={30} width="100" height="48" rx="8" fill="#0c1322" stroke="#1e293b" />
              <text
                x={lane.x}
                y={50}
                textAnchor="middle"
                fontFamily="IBM Plex Sans, sans-serif"
                fontSize="13"
                fontWeight="600"
                fill="#f1f5f9"
              >
                {lane.label}
              </text>
              <text
                x={lane.x}
                y={66}
                textAnchor="middle"
                fontFamily="JetBrains Mono, monospace"
                fontSize="9"
                fill="#64748b"
              >
                {lane.sub}
              </text>
              <line x1={lane.x} y1={TOP} x2={lane.x} y2={BOTTOM} stroke="#1e293b" strokeDasharray="2 4" />
            </g>
          ))}

          {arrows.map((arrow, i) => {
            const fromX = lanes[arrow.from].x
            const toX = lanes[arrow.to].x
            const tone = (arrow as { tone?: string }).tone ?? 'slate'
            const stroke =
              tone === 'cyan' || tone === 'cyan-dashed'
                ? '#22d3ee'
                : tone === 'indigo'
                  ? '#818cf8'
                  : tone === 'emerald'
                    ? '#34d399'
                    : tone === 'amber'
                      ? '#fbbf24'
                      : '#64748b'
            const dash = tone === 'cyan-dashed' ? '5 4' : undefined
            const markerId =
              tone === 'cyan' || tone === 'cyan-dashed'
                ? 'seq-arrow-cyan'
                : tone === 'indigo'
                  ? 'seq-arrow-indigo'
                  : tone === 'emerald'
                    ? 'seq-arrow-emerald'
                    : tone === 'amber'
                      ? 'seq-arrow-amber'
                      : 'seq-arrow-slate'
            const isReverse = toX < fromX
            const labelX = (fromX + toX) / 2
            return (
              <g key={i}>
                <line
                  x1={fromX}
                  y1={arrow.y}
                  x2={toX}
                  y2={arrow.y}
                  stroke={stroke}
                  strokeWidth="1.4"
                  strokeDasharray={dash}
                  markerEnd={`url(#${markerId})`}
                />
                <text
                  x={labelX}
                  y={arrow.y - 6}
                  textAnchor="middle"
                  fontFamily="IBM Plex Sans, sans-serif"
                  fontSize="11"
                  fontWeight="500"
                  fill="#e2e8f0"
                >
                  {arrow.label}
                </text>
                <text
                  x={labelX}
                  y={arrow.y + 12}
                  textAnchor="middle"
                  fontFamily="JetBrains Mono, monospace"
                  fontSize="9"
                  fill={isReverse ? '#94a3b8' : '#64748b'}
                >
                  {arrow.sub}
                </text>
              </g>
            )
          })}

          {/* Phase bands */}
          <PhaseLabel y={108} label="01  INGRESS" />
          <PhaseLabel y={210} label="02  GUARD" />
          <PhaseLabel y={350} label="03  GRAPH OPENS" />
          <PhaseLabel y={490} label="04  TOOL CALL → CRM" />
          <PhaseLabel y={760} label="05  STREAM EMIT" />
          <PhaseLabel y={980} label="06  CLOSE" />
        </svg>
      </div>

      <DiagramFallback title="Text equivalent of request lifecycle">
        Browser opens POST /api/agent/stream as EventSource. Nginx proxies to agent FastAPI on port
        8000 using runtime DNS via $agent_upstream variable. Agent runs evaluate_prompt_safety_decision
        at agent_stream.py:467 and returns decision="pass". A trace event is emitted with the
        trace_id. The agent invokes LangGraph via graph.astream_events with version v2. LangGraph
        emits a reasoning event then calls tool_wrapper(generate_otp) at mcp_manager.py:134, which
        forwards to the MCP server at port 8050. MCP calls the external CRM via httpx Basic-Auth
        POST to /mockfin-service/otp/generate_new/. CRM returns a CSV success row. MCP runs
        _touch(session_id) at server.py:65. The agent emits tool_call, multiple token chunks, a
        cost event, then done.
      </DiagramFallback>
    </div>
  )
}

function PhaseLabel({ y, label }: { y: number; label: string }) {
  return (
    <g>
      <line x1="20" y1={y} x2="60" y2={y} stroke="#22d3ee" strokeOpacity="0.3" strokeWidth="1" />
      <text
        x="20"
        y={y - 6}
        fontFamily="JetBrains Mono, monospace"
        fontSize="9"
        letterSpacing="2"
        fill="#22d3ee"
        opacity="0.7"
      >
        {label}
      </text>
    </g>
  )
}
