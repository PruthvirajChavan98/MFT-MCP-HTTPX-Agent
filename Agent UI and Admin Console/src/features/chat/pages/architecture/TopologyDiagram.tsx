import { DiagramFallback } from './DiagramFallback'

/**
 * Topology — 11-service compose stack laid out as four horizontal bands
 * (edge → frontend → app + observability → data + workers). Hand-tuned
 * positions; every node carries the real logo from public/icons.
 *
 * Geometry note: every node is 140 px wide so its label fits without clipping.
 * `shadow_judge_worker` (19 chars) gets 180 px. The right-column observability
 * trio sits inside the App-Plane band; alertmanager drops one row below
 * prometheus/grafana to keep the band height under 720 px.
 */
export function TopologyDiagram() {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0c1322]/60 p-2 shadow-2xl shadow-black/40 backdrop-blur">
      <div className="overflow-x-auto">
        <svg
          viewBox="0 0 1200 720"
          role="img"
          aria-labelledby="topology-title topology-desc"
          xmlns="http://www.w3.org/2000/svg"
          className="block h-auto w-full min-w-[920px]"
        >
          <title id="topology-title">Compose service topology</title>
          <desc id="topology-desc">
            Cloudflare tunnel ingress fans into the frontend nginx proxy, which routes to the agent
            FastAPI process and a separate FastMCP process. Both connect to a shared data plane of
            Postgres, Redis, and Milvus. Workers and a Prometheus/Grafana/Alertmanager observability
            stack sit alongside.
          </desc>

          <defs>
            <marker
              id="topo-arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M0,0 L10,5 L0,10 z" fill="#22d3ee" />
            </marker>
            <marker
              id="topo-arrow-emerald"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M0,0 L10,5 L0,10 z" fill="#34d399" />
            </marker>
            <marker
              id="topo-arrow-indigo"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M0,0 L10,5 L0,10 z" fill="#818cf8" />
            </marker>
            <linearGradient id="topo-band" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#22d3ee" stopOpacity="0" />
              <stop offset="50%" stopColor="#22d3ee" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* ── Band labels (mono eyebrows) ── */}
          {[
            { y: 60, label: 'EDGE' },
            { y: 200, label: 'FRONTEND' },
            { y: 360, label: 'APP PLANE  +  OBSERVABILITY' },
            { y: 540, label: 'DATA + WORKERS' },
          ].map(({ y, label }) => (
            <g key={label}>
              <line x1="40" y1={y} x2="180" y2={y} stroke="#1e293b" strokeWidth="1" />
              <text
                x="40"
                y={y - 8}
                fontFamily="JetBrains Mono, monospace"
                fontSize="10"
                letterSpacing="2.5"
                fill="#475569"
              >
                {label}
              </text>
            </g>
          ))}

          {/* ── Edge: Cloudflare ── */}
          <Node x={530} y={30} w={140} h={64} icon="cloudflare.svg" label="cloudflared-prod" subtext="tunnel" tone="cyan" />

          {/* Edge → Frontend */}
          <line x1="600" y1="94" x2="600" y2="160" stroke="#22d3ee" strokeWidth="1.5" markerEnd="url(#topo-arrow)" />
          <text
            x="612"
            y="130"
            fontFamily="JetBrains Mono, monospace"
            fontSize="10"
            fill="#94a3b8"
          >
            mft-agent.* / mft-api.*
          </text>

          {/* ── Frontend ── */}
          <Node x={530} y={160} w={140} h={64} icon="nginx-svgrepo-com.svg" label="frontend-prod" subtext="nginx :80" tone="indigo" />

          {/* Frontend → app plane */}
          <line x1="600" y1="224" x2="450" y2="320" stroke="#22d3ee" strokeWidth="1.5" markerEnd="url(#topo-arrow)" />
          <line x1="600" y1="224" x2="750" y2="320" stroke="#22d3ee" strokeWidth="1.5" markerEnd="url(#topo-arrow)" />

          {/* ── App plane band tint ── */}
          <rect x="60" y="290" width="1080" height="180" rx="12" fill="url(#topo-band)" opacity="0.45" />

          {/* App plane: agent + mcp */}
          <Node x={380} y={320} w={140} h={64} icon="FastAPI.svg" label="agent" subtext=":8000  uvicorn" tone="cyan" />
          <Node x={680} y={320} w={140} h={64} icon="mcp.webp" label="mcp" subtext=":8050  FastMCP SSE" tone="emerald" />

          {/* Inner plane label */}
          <text
            x="600"
            y="312"
            textAnchor="middle"
            fontFamily="JetBrains Mono, monospace"
            fontSize="10"
            fill="#475569"
            letterSpacing="2"
          >
            TWO PROCESSES — NO SHARED POOLS
          </text>

          {/* agent ⇄ mcp */}
          <line x1="520" y1="352" x2="680" y2="352" stroke="#34d399" strokeWidth="1.2" strokeDasharray="3 3" />
          <text x="600" y="346" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#94a3b8">
            tools.ainvoke()
          </text>

          {/* agent → outbound CRM (dashed) */}
          <line x1="380" y1="320" x2="200" y2="240" stroke="#22d3ee" strokeWidth="1.2" strokeDasharray="4 4" />
          <text x="180" y="232" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#22d3ee">
            external CRM ↗
          </text>
          <text x="180" y="246" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#64748b">
            test-mock-crm.*
          </text>

          {/* App → data plane */}
          <line x1="450" y1="384" x2="265" y2="510" stroke="#818cf8" strokeWidth="1.5" markerEnd="url(#topo-arrow-indigo)" />
          <line x1="450" y1="384" x2="405" y2="510" stroke="#818cf8" strokeWidth="1.5" markerEnd="url(#topo-arrow-indigo)" />
          <line x1="450" y1="384" x2="540" y2="510" stroke="#818cf8" strokeWidth="1.5" markerEnd="url(#topo-arrow-indigo)" />

          <line x1="750" y1="384" x2="405" y2="510" stroke="#818cf8" strokeWidth="1.2" markerEnd="url(#topo-arrow-indigo)" opacity="0.5" />
          <line x1="750" y1="384" x2="540" y2="510" stroke="#818cf8" strokeWidth="1.2" markerEnd="url(#topo-arrow-indigo)" opacity="0.5" />

          {/* ── Right column: Observability ── */}
          <Node x={920} y={310} w={130} h={56} icon="prometheus.svg" label="prometheus" subtext=":9090" tone="amber" />
          <Node x={1060} y={310} w={130} h={56} icon="grafana.svg" label="grafana" subtext=":3000" tone="amber" />
          <Node x={990} y={400} w={140} h={56} icon="prometheus.svg" label="alertmanager" subtext=":9093" tone="rose" />

          {/* agent → prometheus (scrape) */}
          <line x1="520" y1="338" x2="920" y2="338" stroke="#fbbf24" strokeWidth="1" strokeDasharray="2 3" />
          <text x="912" y="332" textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#94a3b8">
            scrape /metrics
          </text>

          {/* prometheus → grafana */}
          <line x1="1050" y1="338" x2="1060" y2="338" stroke="#fbbf24" strokeWidth="1.2" markerEnd="url(#topo-arrow)" />

          {/* prometheus → alertmanager */}
          <line x1="985" y1="366" x2="1040" y2="400" stroke="#f87171" strokeWidth="1" />

          {/* ── Data + workers row ── */}
          {/* db-migrate (init container glyph — dashed, no logo) */}
          <rect x="60" y="510" width="140" height="64" rx="8" fill="#0c1322" stroke="#1e293b" strokeWidth="1" strokeDasharray="3 3" />
          <text x="130" y="535" textAnchor="middle" fontFamily="IBM Plex Sans, sans-serif" fontSize="13" fontWeight="600" fill="#cbd5e1">
            db-migrate
          </text>
          <text x="130" y="552" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#64748b">
            init container
          </text>
          <text x="130" y="566" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#64748b">
            postgres:18.3
          </text>
          <line x1="200" y1="540" x2="220" y2="540" stroke="#818cf8" strokeWidth="1" markerEnd="url(#topo-arrow-indigo)" />

          <Node x={220} y={510} w={130} h={64} icon="postgresql-logo-svgrepo-com.svg" label="postgres" subtext=":5432" tone="indigo" />
          <Node x={370} y={510} w={120} h={64} icon="Redis.svg" label="redis" subtext=":6379" tone="emerald" />
          <Node x={510} y={510} w={130} h={64} icon="milvus.png" label="milvus" subtext="vector store" tone="indigo" />
          <Node x={660} y={510} w={180} h={64} icon="langgraph.svg" label="shadow_judge_worker" subtext="trace eval" tone="emerald" />

          {/* shadow_judge → postgres + redis (consumes queue, mirrors results) */}
          <line x1="740" y1="574" x2="430" y2="574" stroke="#34d399" strokeWidth="1" strokeDasharray="2 3" markerEnd="url(#topo-arrow-emerald)" />
          <line x1="740" y1="574" x2="285" y2="574" stroke="#34d399" strokeWidth="1" strokeDasharray="2 3" markerEnd="url(#topo-arrow-emerald)" />

          {/* geoip glyph */}
          <rect x="860" y="510" width="140" height="64" rx="8" fill="#0c1322" stroke="#1e293b" strokeWidth="1" />
          <text x="930" y="535" textAnchor="middle" fontFamily="IBM Plex Sans, sans-serif" fontSize="13" fontWeight="600" fill="#cbd5e1">
            geoip_updater
          </text>
          <text x="930" y="552" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#64748b">
            daily refresh
          </text>

          {/* Footer: networks */}
          <g transform="translate(60, 670)">
            <circle cx="6" cy="0" r="5" fill="#22d3ee" opacity="0.5" />
            <text x="18" y="4" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#94a3b8">
              mft_net
            </text>
            <circle cx="120" cy="0" r="5" fill="#818cf8" opacity="0.5" />
            <text x="132" y="4" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#94a3b8">
              databases
            </text>
            <text x="280" y="4" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#475569">
              dashed = outbound external · solid = intra-network
            </text>
          </g>
        </svg>
      </div>

      <DiagramFallback title="Text equivalent of compose topology">
        Edge: cloudflared-prod (Cloudflare tunnel). Frontend: frontend-prod nginx :80, routes
        /api/agent/stream and the React bundle. App plane: agent (FastAPI :8000) and mcp (FastMCP
        :8050) — separate processes, no shared connection pools. agent calls mcp via tools.ainvoke
        and reaches the external CRM via outbound HTTPS. Observability: prometheus scrapes /metrics
        from the agent, grafana queries prometheus, alertmanager handles routing rules. Data plane:
        postgres, redis, milvus. Workers: shadow_judge_worker (consumes trace queue),
        geoip_updater (daily). db-migrate is an init container that bootstraps schema. Networks:
        mft_net + databases.
      </DiagramFallback>
    </div>
  )
}

const TONE_STROKE = {
  cyan: '#22d3ee',
  indigo: '#818cf8',
  emerald: '#34d399',
  amber: '#fbbf24',
  rose: '#f87171',
} as const

interface NodeProps {
  x: number
  y: number
  w: number
  h: number
  icon: string
  label: string
  subtext?: string
  tone: keyof typeof TONE_STROKE
}

function Node({ x, y, w, h, icon, label, subtext, tone }: NodeProps) {
  const stroke = TONE_STROKE[tone]
  const labelX = x + 44
  const labelY = h <= 56 ? y + 22 : y + 26
  const subY = h <= 56 ? y + 38 : y + 44
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx="10"
        fill="#0c1322"
        stroke={stroke}
        strokeOpacity="0.45"
        strokeWidth="1"
      />
      <image
        href={`/icons/${icon}`}
        x={x + 12}
        y={y + (h - 24) / 2}
        width="24"
        height="24"
        preserveAspectRatio="xMidYMid meet"
      />
      <text
        x={labelX}
        y={labelY}
        fontFamily="IBM Plex Sans, sans-serif"
        fontSize="13"
        fontWeight="600"
        fill="#f1f5f9"
      >
        {label}
      </text>
      {subtext && (
        <text
          x={labelX}
          y={subY}
          fontFamily="JetBrains Mono, monospace"
          fontSize="10"
          fill="#94a3b8"
        >
          {subtext}
        </text>
      )}
    </g>
  )
}
