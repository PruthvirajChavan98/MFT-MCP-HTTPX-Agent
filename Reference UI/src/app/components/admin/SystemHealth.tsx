import { useState, useEffect } from "react";
import { Heart, CheckCircle, XCircle, Clock, RefreshCw, Server, Database, Globe, Wifi } from "lucide-react";
import { mockHealthStatus } from "../../lib/api";

const DEPENDENCY_ICONS: Record<string, typeof Database> = {
  redis: Database,
  qdrant: Database,
  openrouter: Globe,
  postgres: Server,
};

export function SystemHealth() {
  const [health] = useState(mockHealthStatus);
  const [lastChecked, setLastChecked] = useState(new Date());
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      setLastChecked(new Date());
    }, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const uptimeDays = Math.floor(health.uptime_seconds / 86400);
  const uptimeHours = Math.floor((health.uptime_seconds % 86400) / 3600);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-gray-900" style={{ fontWeight: 700 }}>System Health</h1>
          <p className="text-gray-500" style={{ fontSize: 14 }}>
            Service health monitoring &middot; v{health.version}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer" style={{ fontSize: 13 }}>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 accent-brand-main"
            />
            Auto-refresh (30s)
          </label>
          <button
            onClick={() => setLastChecked(new Date())}
            className="px-3 py-2 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 flex items-center gap-2"
            style={{ fontSize: 13 }}
          >
            <RefreshCw className="w-4 h-4" /> Check Now
          </button>
        </div>
      </div>

      {/* Overall Status */}
      <div
        className="rounded-2xl p-6 text-white relative overflow-hidden"
        style={{ background: health.status === "healthy" ? "var(--brand-gradient)" : "#ef4444" }}
      >
        <div className="absolute top-4 right-4 opacity-10">
          <Heart className="w-24 h-24" />
        </div>
        <div className="relative">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center">
              {health.status === "healthy" ? (
                <CheckCircle className="w-6 h-6" />
              ) : (
                <XCircle className="w-6 h-6" />
              )}
            </div>
            <div>
              <div className="text-white/80" style={{ fontSize: 12 }}>Overall Status</div>
              <div className="text-2xl capitalize" style={{ fontWeight: 700 }}>{health.status}</div>
            </div>
          </div>
          <div className="flex flex-wrap gap-6 mt-4">
            <div>
              <div className="text-white/70" style={{ fontSize: 11 }}>Uptime</div>
              <div style={{ fontWeight: 600 }}>{uptimeDays} days, {uptimeHours} hours</div>
            </div>
            <div>
              <div className="text-white/70" style={{ fontSize: 11 }}>Version</div>
              <div style={{ fontWeight: 600 }}>v{health.version}</div>
            </div>
            <div>
              <div className="text-white/70" style={{ fontSize: 11 }}>Last Checked</div>
              <div style={{ fontWeight: 600 }}>{lastChecked.toLocaleTimeString()}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Dependencies */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(health.dependencies).map(([name, dep]) => {
          const Icon = DEPENDENCY_ICONS[name] || Server;
          const isHealthy = dep.status === "connected";
          return (
            <div key={name} className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: isHealthy ? "#dcfce7" : "#fef2f2" }}
                  >
                    <Icon className="w-4 h-4" style={{ color: isHealthy ? "#16a34a" : "#ef4444" }} />
                  </div>
                  <div>
                    <div className="text-gray-900 capitalize" style={{ fontSize: 14, fontWeight: 600 }}>{name}</div>
                  </div>
                </div>
                {isHealthy ? (
                  <CheckCircle className="w-5 h-5 text-green-500" />
                ) : (
                  <XCircle className="w-5 h-5 text-red-500" />
                )}
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-gray-500" style={{ fontSize: 12 }}>Status</span>
                  <span
                    className={`px-2 py-0.5 rounded-full ${
                      isHealthy ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                    }`}
                    style={{ fontSize: 11, fontWeight: 500 }}
                  >
                    {dep.status}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500" style={{ fontSize: 12 }}>Latency</span>
                  <span
                    className={`${
                      dep.latency_ms < 10 ? "text-green-600" :
                      dep.latency_ms < 50 ? "text-yellow-600" :
                      "text-orange-600"
                    }`}
                    style={{ fontSize: 13, fontWeight: 600 }}
                  >
                    {dep.latency_ms}ms
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Endpoints */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="text-gray-900" style={{ fontWeight: 600 }}>Health Endpoints</h3>
        </div>
        <div className="divide-y divide-gray-50">
          {[
            { endpoint: "GET /health", desc: "Basic health check", status: "200 OK" },
            { endpoint: "GET /health/live", desc: "Liveness probe (Kubernetes)", status: "200 OK" },
            { endpoint: "GET /health/ready", desc: "Readiness probe with dependency checks", status: "200 OK" },
            { endpoint: "GET /metrics", desc: "Prometheus metrics endpoint", status: "200 OK" },
            { endpoint: "GET /rate-limit/health", desc: "Rate limit infrastructure health", status: "200 OK" },
          ].map((ep) => (
            <div key={ep.endpoint} className="px-5 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors">
              <div className="flex items-center gap-3">
                <code className="text-brand-dark bg-brand-light/10 px-2 py-0.5 rounded" style={{ fontSize: 12 }}>
                  {ep.endpoint}
                </code>
                <span className="text-gray-500" style={{ fontSize: 12 }}>{ep.desc}</span>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-green-100 text-green-700" style={{ fontSize: 11, fontWeight: 500 }}>
                {ep.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* API Information */}
      <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <h3 className="text-gray-900 mb-3" style={{ fontWeight: 600 }}>API Configuration</h3>
        <div className="grid sm:grid-cols-2 gap-3">
          {[
            { label: "Base URL", value: "http://localhost:8000" },
            { label: "Admin Key Header", value: "X-Admin-Key" },
            { label: "OpenRouter Key Header", value: "X-OpenRouter-Key" },
            { label: "Eval Ingest Key Header", value: "X-Eval-Ingest-Key" },
          ].map((cfg) => (
            <div key={cfg.label} className="bg-gray-50 rounded-lg p-3">
              <div className="text-gray-400" style={{ fontSize: 10 }}>{cfg.label}</div>
              <code className="text-gray-700" style={{ fontSize: 12 }}>{cfg.value}</code>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
