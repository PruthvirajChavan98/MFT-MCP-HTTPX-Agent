import { useState } from "react";
import { Gauge, RefreshCw, Shield, Zap, Settings, RotateCcw } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { mockRateLimitMetrics } from "../../lib/api";

export function RateLimiting() {
  const [metrics] = useState(mockRateLimitMetrics);

  const rpsHistory = [
    { time: "00:00", rps: 8.2, blocked: 0.3 },
    { time: "04:00", rps: 3.1, blocked: 0.1 },
    { time: "08:00", rps: 18.5, blocked: 1.2 },
    { time: "10:00", rps: 32.4, blocked: 2.8 },
    { time: "12:00", rps: 45.2, blocked: 4.1 },
    { time: "14:00", rps: 38.7, blocked: 3.2 },
    { time: "16:00", rps: 28.9, blocked: 1.9 },
    { time: "18:00", rps: 22.3, blocked: 1.1 },
    { time: "20:00", rps: 15.6, blocked: 0.5 },
    { time: "22:00", rps: 12.4, blocked: 0.2 },
  ];

  const mockLimiters = [
    { id: "session:sess_a1b2c3", remaining: 22, limit: 30, window: "60s", status: "ok" },
    { id: "session:sess_d4e5f6", remaining: 5, limit: 30, window: "60s", status: "warning" },
    { id: "session:sess_g7h8i9", remaining: 28, limit: 30, window: "60s", status: "ok" },
    { id: "global:all", remaining: 850, limit: 1000, window: "60s", status: "ok" },
    { id: "session:sess_m3n4o5", remaining: 0, limit: 30, window: "60s", status: "blocked" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-gray-900" style={{ fontWeight: 700 }}>Rate Limiting</h1>
          <p className="text-gray-500" style={{ fontSize: 14 }}>Monitor and manage rate limiters</p>
        </div>
        <button
          className="px-3 py-2 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 flex items-center gap-2"
          style={{ fontSize: 13 }}
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Total Requests", value: metrics.total_requests.toLocaleString(), icon: Zap, color: "#3b82f6" },
          { label: "Blocked Requests", value: metrics.blocked_requests.toString(), icon: Shield, color: "#ef4444" },
          { label: "Current RPS", value: metrics.current_rps.toString(), icon: Gauge, color: "#10b981" },
          { label: "Peak RPS", value: metrics.peak_rps.toString(), icon: Gauge, color: "#f59e0b" },
        ].map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: stat.color + "20" }}>
                <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
              </div>
              <span className="text-gray-500" style={{ fontSize: 12 }}>{stat.label}</span>
            </div>
            <div className="text-gray-900" style={{ fontSize: 24, fontWeight: 700 }}>{stat.value}</div>
          </div>
        ))}
      </div>

      {/* RPS Chart */}
      <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>Requests Per Second (Today)</h3>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={rpsHistory}>
            <defs>
              <linearGradient id="rpsGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="oklch(78.9% 0.154 211.53)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="oklch(78.9% 0.154 211.53)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }} />
            <Area type="monotone" dataKey="rps" stroke="oklch(78.9% 0.154 211.53)" fill="url(#rpsGrad)" name="RPS" />
            <Area type="monotone" dataKey="blocked" stroke="#ef4444" fill="#ef444420" name="Blocked RPS" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Config */}
      <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Settings className="w-5 h-5 text-gray-500" />
          <h3 className="text-gray-900" style={{ fontWeight: 600 }}>Rate Limit Configuration</h3>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Global RPM", value: metrics.config.global_rpm, unit: "req/min" },
            { label: "Session RPM", value: metrics.config.session_rpm, unit: "req/min" },
            { label: "Burst Limit", value: metrics.config.burst_limit, unit: "requests" },
            { label: "Window", value: metrics.config.window_seconds, unit: "seconds" },
          ].map((cfg) => (
            <div key={cfg.label} className="bg-gray-50 rounded-lg p-3">
              <div className="text-gray-500" style={{ fontSize: 11 }}>{cfg.label}</div>
              <div className="flex items-baseline gap-1">
                <span className="text-gray-900" style={{ fontSize: 20, fontWeight: 700 }}>{cfg.value}</span>
                <span className="text-gray-400" style={{ fontSize: 11 }}>{cfg.unit}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Active Limiters */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="text-gray-900" style={{ fontWeight: 600 }}>Active Rate Limiters</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Identifier</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Remaining</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Limit</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Window</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Status</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Usage</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {mockLimiters.map((limiter) => {
                const usagePct = ((limiter.limit - limiter.remaining) / limiter.limit) * 100;
                return (
                  <tr key={limiter.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3">
                      <code className="text-gray-700" style={{ fontSize: 12 }}>{limiter.id}</code>
                    </td>
                    <td className="px-5 py-3 text-gray-900" style={{ fontSize: 13, fontWeight: 500 }}>
                      {limiter.remaining}
                    </td>
                    <td className="px-5 py-3 text-gray-600" style={{ fontSize: 13 }}>{limiter.limit}</td>
                    <td className="px-5 py-3 text-gray-600" style={{ fontSize: 13 }}>{limiter.window}</td>
                    <td className="px-5 py-3">
                      <span
                        className={`px-2 py-0.5 rounded-full ${
                          limiter.status === "ok" ? "bg-green-100 text-green-700" :
                          limiter.status === "warning" ? "bg-yellow-100 text-yellow-700" :
                          "bg-red-100 text-red-700"
                        }`}
                        style={{ fontSize: 11, fontWeight: 500 }}
                      >
                        {limiter.status}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="w-24">
                        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${usagePct}%`,
                              backgroundColor: usagePct > 80 ? "#ef4444" : usagePct > 50 ? "#f59e0b" : "#10b981",
                            }}
                          />
                        </div>
                        <span className="text-gray-400" style={{ fontSize: 10 }}>{usagePct.toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <button className="w-7 h-7 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-400 hover:text-brand-dark" title="Reset">
                        <RotateCcw className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
