import { useState } from "react";
import { Shield, AlertTriangle, AlertOctagon, Info, Filter, BarChart3, Eye } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { mockGuardrails } from "../../lib/api";

const SEVERITY_CONFIG: Record<string, { color: string; bg: string; icon: typeof AlertTriangle }> = {
  critical: { color: "#ef4444", bg: "#fef2f2", icon: AlertOctagon },
  high: { color: "#f97316", bg: "#fff7ed", icon: AlertTriangle },
  medium: { color: "#f59e0b", bg: "#fffbeb", icon: AlertTriangle },
  low: { color: "#3b82f6", bg: "#eff6ff", icon: Info },
};

const TRIGGER_COLORS: Record<string, string> = {
  off_topic: "#818cf8",
  pii_detected: "#ef4444",
  prompt_injection: "#f97316",
  competitor_mention: "#f59e0b",
};

export function GuardrailsPage() {
  const [guardrails] = useState(mockGuardrails);
  const [severityFilter, setSeverityFilter] = useState("all");

  const filtered = guardrails.filter((g) =>
    severityFilter === "all" || g.severity === severityFilter
  );

  const triggerCounts = Object.entries(
    guardrails.reduce<Record<string, number>>((acc, g) => {
      acc[g.trigger] = (acc[g.trigger] || 0) + 1;
      return acc;
    }, {})
  ).map(([name, value]) => ({ name: name.replace(/_/g, " "), value }));

  const actionCounts = Object.entries(
    guardrails.reduce<Record<string, number>>((acc, g) => {
      acc[g.action] = (acc[g.action] || 0) + 1;
      return acc;
    }, {})
  ).map(([name, value]) => ({ name, value }));

  const dailyTriggers = [
    { day: "Mon", count: 12 },
    { day: "Tue", count: 8 },
    { day: "Wed", count: 15 },
    { day: "Thu", count: 6 },
    { day: "Fri", count: 18 },
    { day: "Sat", count: 22 },
    { day: "Sun", count: 8 },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-gray-900" style={{ fontWeight: 700 }}>Guardrails</h1>
        <p className="text-gray-500" style={{ fontSize: 14 }}>Content safety monitoring & guardrail events</p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Total Triggers", value: guardrails.length, color: "#f59e0b" },
          { label: "Critical", value: guardrails.filter((g) => g.severity === "critical").length, color: "#ef4444" },
          { label: "Blocked", value: guardrails.filter((g) => g.action === "blocked").length, color: "#f97316" },
          { label: "PII Detected", value: guardrails.filter((g) => g.trigger === "pii_detected").length, color: "#818cf8" },
        ].map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: stat.color + "20" }}>
                <Shield className="w-4 h-4" style={{ color: stat.color }} />
              </div>
              <span className="text-gray-500" style={{ fontSize: 12 }}>{stat.label}</span>
            </div>
            <div className="text-gray-900" style={{ fontSize: 24, fontWeight: 700 }}>{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>Daily Triggers</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={dailyTriggers}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Bar dataKey="count" fill="#f59e0b" radius={[4, 4, 0, 0]} name="Triggers" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>By Trigger Type</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={triggerCounts} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={40} outerRadius={70} paddingAngle={3}>
                {triggerCounts.map((_, i) => (
                  <Cell key={i} fill={Object.values(TRIGGER_COLORS)[i % Object.values(TRIGGER_COLORS).length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-3 mt-2 justify-center">
            {triggerCounts.map((t, i) => (
              <div key={t.name} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: Object.values(TRIGGER_COLORS)[i % Object.values(TRIGGER_COLORS).length] }} />
                <span className="text-gray-600 capitalize" style={{ fontSize: 11 }}>{t.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Events Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h3 className="text-gray-900" style={{ fontWeight: 600 }}>Guardrail Events</h3>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            {["all", "critical", "high", "medium", "low"].map((s) => (
              <button
                key={s}
                onClick={() => setSeverityFilter(s)}
                className={`px-2 py-1 rounded-lg capitalize ${
                  severityFilter === s ? "text-white" : "text-gray-500 bg-gray-100 hover:bg-gray-200"
                }`}
                style={severityFilter === s ? { background: "var(--brand-gradient)", fontSize: 12 } : { fontSize: 12 }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Severity</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Trigger</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Input</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Action</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Session</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Time</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((gr) => {
                const config = SEVERITY_CONFIG[gr.severity];
                return (
                  <tr key={gr.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3">
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full capitalize"
                        style={{
                          fontSize: 11,
                          fontWeight: 500,
                          backgroundColor: config.bg,
                          color: config.color,
                        }}
                      >
                        <config.icon className="w-3 h-3" />
                        {gr.severity}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-gray-700 capitalize" style={{ fontSize: 13 }}>
                      {gr.trigger.replace(/_/g, " ")}
                    </td>
                    <td className="px-5 py-3 text-gray-600 max-w-xs truncate" style={{ fontSize: 13 }}>
                      {gr.input}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`px-2 py-0.5 rounded-full capitalize ${
                          gr.action === "blocked" ? "bg-red-100 text-red-700" :
                          gr.action === "redacted" ? "bg-yellow-100 text-yellow-700" :
                          "bg-blue-100 text-blue-700"
                        }`}
                        style={{ fontSize: 11, fontWeight: 500 }}
                      >
                        {gr.action}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <code className="text-brand-dark" style={{ fontSize: 11 }}>{gr.session_id}</code>
                    </td>
                    <td className="px-5 py-3 text-gray-500" style={{ fontSize: 12 }}>
                      {new Date(gr.timestamp).toLocaleString()}
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
