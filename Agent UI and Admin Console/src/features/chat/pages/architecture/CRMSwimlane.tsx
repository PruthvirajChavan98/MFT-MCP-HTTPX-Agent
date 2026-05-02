import { DiagramFallback } from './DiagramFallback'

/**
 * CRM bridge swimlane: MCP container → outbound HTTPS:443 → external CRM.
 * Shows the two auth schemes side-by-side (Basic for public, Bearer for
 * session-gated) and the httpx.Timeout profile.
 */
export function CRMSwimlane() {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0c1322]/60 p-2 shadow-2xl shadow-black/40 backdrop-blur">
      <div className="overflow-x-auto">
        <svg
          viewBox="0 0 880 320"
          role="img"
          aria-labelledby="crm-title crm-desc"
          xmlns="http://www.w3.org/2000/svg"
          className="block h-auto w-full min-w-[640px]"
        >
          <title id="crm-title">CRM bridge — MCP outbound HTTPS to external CRM</title>
          <desc id="crm-desc">
            The MCP container makes outbound HTTPS calls on port 443 to the external CRM at
            test-mock-crm.pruthvirajchavan.codes. Public tools use HTTP Basic auth with the
            BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD environment variables. Session-gated
            tools use a Bearer token obtained at OTP validation and stored in the Redis session.
            Timeout profile: connect five seconds, read twenty-five seconds, write ten seconds,
            pool five seconds.
          </desc>

          <defs>
            <marker id="crm-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#22d3ee" />
            </marker>
          </defs>

          {/* Lane labels */}
          <text x="40" y="36" fontFamily="JetBrains Mono, monospace" fontSize="10" letterSpacing="2.5" fill="#475569">
            INSIDE COMPOSE
          </text>
          <line x1="40" y1="44" x2="200" y2="44" stroke="#1e293b" />
          <text x="660" y="36" fontFamily="JetBrains Mono, monospace" fontSize="10" letterSpacing="2.5" fill="#475569">
            EXTERNAL · INTERNET
          </text>
          <line x1="660" y1="44" x2="840" y2="44" stroke="#1e293b" />

          {/* Boundary line */}
          <line x1="430" y1="60" x2="430" y2="290" stroke="#22d3ee" strokeOpacity="0.25" strokeDasharray="2 5" />
          <text
            x="436"
            y="298"
            fontFamily="JetBrains Mono, monospace"
            fontSize="10"
            fill="#22d3ee"
            opacity="0.7"
          >
            ↑ Docker network boundary
          </text>

          {/* MCP node */}
          <rect x="60" y="100" width="180" height="140" rx="10" fill="#0c1322" stroke="#34d399" />
          <image href="/icons/mcp.webp" x="76" y="116" width="24" height="24" />
          <text x="108" y="134" fontFamily="IBM Plex Sans, sans-serif" fontSize="14" fontWeight="600" fill="#f1f5f9">
            mcp
          </text>
          <text x="76" y="160" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#94a3b8">
            FastMCP :8050
          </text>
          <text x="76" y="178" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#94a3b8">
            httpx.AsyncClient
          </text>
          <text x="76" y="200" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#22d3ee">
            connect=5s read=25s
          </text>
          <text x="76" y="214" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#22d3ee">
            write=10s pool=5s
          </text>
          <text x="76" y="232" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#64748b">
            auth_api.py:74-98
          </text>

          {/* Outbound arrow */}
          <line x1="240" y1="140" x2="640" y2="140" stroke="#22d3ee" strokeWidth="1.6" strokeDasharray="6 4" markerEnd="url(#crm-arrow)" />
          <text x="440" y="128" textAnchor="middle" fontFamily="IBM Plex Sans, sans-serif" fontSize="12" fontWeight="500" fill="#e2e8f0">
            HTTPS :443
          </text>
          <text x="440" y="156" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#22d3ee">
            Authorization: Basic crm:crm  (public tools)
          </text>
          <text x="440" y="170" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#34d399">
            Authorization: Bearer &lt;session_token&gt;  (session-gated tools)
          </text>

          <line x1="640" y1="200" x2="240" y2="200" stroke="#475569" strokeWidth="1" strokeDasharray="3 4" markerEnd="url(#crm-arrow)" />
          <text x="440" y="218" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#94a3b8">
            CSV / JSON response
          </text>

          {/* CRM node */}
          <rect x="640" y="100" width="200" height="140" rx="10" fill="#0c1322" stroke="#22d3ee" />
          <image href="/icons/cloudflare.svg" x="656" y="116" width="22" height="22" opacity="0.7" />
          <text x="686" y="134" fontFamily="IBM Plex Sans, sans-serif" fontSize="14" fontWeight="600" fill="#f1f5f9">
            CRM
          </text>
          <text x="656" y="160" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#94a3b8">
            test-mock-crm.
          </text>
          <text x="656" y="174" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#94a3b8">
            pruthvirajchavan.codes
          </text>
          <text x="656" y="196" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#22d3ee">
            /mockfin-service/otp/*
          </text>
          <text x="656" y="210" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#34d399">
            /mockfin-service/loan/*
          </text>
          <text x="656" y="226" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#64748b">
            core_api.py:62-450
          </text>

          {/* Bottom note: env-var requirement */}
          <rect x="60" y="270" width="780" height="38" rx="6" fill="#0c1322" stroke="#1e293b" strokeDasharray="3 3" />
          <text x="76" y="294" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#94a3b8">
            BASIC_AUTH_USERNAME / BASIC_AUTH_PASSWORD missing → MCP refuses to start (RuntimeError, auth_api.py:59-68)
          </text>
        </svg>
      </div>

      <DiagramFallback title="Text equivalent of CRM bridge">
        Inside Docker compose, the mcp container (FastMCP on port 8050) uses httpx.AsyncClient to
        call the external CRM at test-mock-crm.pruthvirajchavan.codes over HTTPS port 443. Public
        tools attach Authorization: Basic with crm:crm. Session-gated tools attach Authorization:
        Bearer with the token obtained at OTP validation. The httpx Timeout profile is connect=5s,
        read=25s, write=10s, pool=5s. If BASIC_AUTH_USERNAME or BASIC_AUTH_PASSWORD is missing,
        MCP refuses to start with a RuntimeError at auth_api.py:59-68.
      </DiagramFallback>
    </div>
  )
}
