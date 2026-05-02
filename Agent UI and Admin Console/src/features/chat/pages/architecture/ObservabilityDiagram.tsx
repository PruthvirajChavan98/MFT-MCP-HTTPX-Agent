import { DiagramFallback } from './DiagramFallback'

export function ObservabilityDiagram() {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0c1322]/60 p-2 shadow-xl shadow-black/30 backdrop-blur">
      <div className="overflow-x-auto">
        <svg
          viewBox="0 0 720 240"
          role="img"
          aria-labelledby="obs-title obs-desc"
          xmlns="http://www.w3.org/2000/svg"
          className="block h-auto w-full min-w-[520px]"
        >
          <title id="obs-title">Observability stack</title>
          <desc id="obs-desc">
            The agent exposes a Prometheus metrics endpoint. Prometheus scrapes it on a schedule.
            Grafana queries Prometheus for dashboards. Alertmanager handles alert routing rules
            from Prometheus.
          </desc>

          <defs>
            <marker id="obs-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#fbbf24" />
            </marker>
          </defs>

          {/* agent */}
          <rect x="40" y="80" width="140" height="80" rx="10" fill="#0c1322" stroke="#22d3ee" />
          <image href="/icons/FastAPI.svg" x="56" y="96" width="22" height="22" />
          <text x="86" y="114" fontFamily="IBM Plex Sans, sans-serif" fontSize="13" fontWeight="600" fill="#f1f5f9">
            agent
          </text>
          <text x="56" y="138" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#94a3b8">
            /metrics endpoint
          </text>
          <text x="56" y="152" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#64748b">
            histograms, counters
          </text>

          {/* prometheus */}
          <rect x="280" y="80" width="140" height="80" rx="10" fill="#0c1322" stroke="#fbbf24" />
          <image href="/icons/prometheus.svg" x="296" y="96" width="22" height="22" />
          <text x="326" y="114" fontFamily="IBM Plex Sans, sans-serif" fontSize="13" fontWeight="600" fill="#f1f5f9">
            prometheus
          </text>
          <text x="296" y="138" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#94a3b8">
            :9090  scrape loop
          </text>
          <text x="296" y="152" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#64748b">
            v2.53.1
          </text>

          {/* grafana */}
          <rect x="540" y="40" width="140" height="80" rx="10" fill="#0c1322" stroke="#fbbf24" />
          <image href="/icons/grafana.svg" x="556" y="56" width="22" height="22" />
          <text x="586" y="74" fontFamily="IBM Plex Sans, sans-serif" fontSize="13" fontWeight="600" fill="#f1f5f9">
            grafana
          </text>
          <text x="556" y="98" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#94a3b8">
            :3000  dashboards
          </text>
          <text x="556" y="112" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#64748b">
            11.1.4
          </text>

          {/* alertmanager */}
          <rect x="540" y="140" width="140" height="80" rx="10" fill="#0c1322" stroke="#f87171" />
          <text x="560" y="170" fontFamily="IBM Plex Sans, sans-serif" fontSize="13" fontWeight="600" fill="#f1f5f9">
            alertmanager
          </text>
          <text x="556" y="194" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#94a3b8">
            :9093  routing
          </text>
          <text x="556" y="208" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#64748b">
            v0.28.0
          </text>

          {/* arrows */}
          <line x1="180" y1="120" x2="280" y2="120" stroke="#fbbf24" strokeWidth="1.4" markerEnd="url(#obs-arrow)" />
          <text x="230" y="112" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#94a3b8">
            scrape
          </text>

          <line x1="420" y1="100" x2="540" y2="80" stroke="#fbbf24" strokeWidth="1.4" markerEnd="url(#obs-arrow)" />
          <text x="480" y="80" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#94a3b8">
            PromQL
          </text>

          <line x1="420" y1="140" x2="540" y2="170" stroke="#f87171" strokeWidth="1.4" markerEnd="url(#obs-arrow)" />
          <text x="480" y="168" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#94a3b8">
            alerts
          </text>
        </svg>
      </div>
      <DiagramFallback title="Text equivalent of observability stack">
        The agent exposes a /metrics endpoint that Prometheus scrapes on a recurring schedule.
        Grafana issues PromQL queries against Prometheus to render dashboards. Prometheus pushes
        firing alerts to Alertmanager, which handles routing rules. Versions: Prometheus 2.53.1,
        Grafana 11.1.4, Alertmanager 0.28.0.
      </DiagramFallback>
    </div>
  )
}
