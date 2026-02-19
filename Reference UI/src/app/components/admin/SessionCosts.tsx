import { useState } from "react";
import { DollarSign, TrendingUp, Clock, Trash2, RefreshCw, Filter, Download } from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar
} from "recharts";
import { mockSessions, mockCostHistory } from "../../lib/api";

export function SessionCosts() {
  const [sessions] = useState(mockSessions);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");

  const totalCost = sessions.reduce((acc, s) => acc + s.total_cost, 0);
  const totalQueries = sessions.reduce((acc, s) => acc + s.queries, 0);
  const avgCostPerQuery = totalCost / totalQueries;

  const filtered = sessions.filter((s) =>
    statusFilter === "all" || s.status === statusFilter
  );

  // Mock per-session cost history
  const sessionCostHistory = [
    { time: "08:00", cost: 0.05, tokens: 1200 },
    { time: "09:00", cost: 0.12, tokens: 2800 },
    { time: "10:00", cost: 0.08, tokens: 1900 },
    { time: "11:00", cost: 0.15, tokens: 3400 },
    { time: "12:00", cost: 0.06, tokens: 1400 },
    { time: "13:00", cost: 0.03, tokens: 800 },
    { time: "14:00", cost: 0.03, tokens: 700 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-gray-900" style={{ fontWeight: 700 }}>Session Costs</h1>
          <p className="text-gray-500" style={{ fontSize: 14 }}>Track spending per session & global summary</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="px-3 py-2 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 transition-all flex items-center gap-2"
            style={{ fontSize: 13 }}
          >
            <Download className="w-4 h-4" /> Export Report
          </button>
          <button
            className="px-3 py-2 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 transition-all flex items-center gap-2"
            style={{ fontSize: 13 }}
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Total Spend", value: `$${totalCost.toFixed(2)}`, icon: DollarSign, color: "#f59e0b" },
          { label: "Total Queries", value: totalQueries.toLocaleString(), icon: TrendingUp, color: "#3b82f6" },
          { label: "Avg Cost/Query", value: `$${avgCostPerQuery.toFixed(4)}`, icon: DollarSign, color: "#10b981" },
          { label: "Active Sessions", value: sessions.filter((s) => s.status === "active").length.toString(), icon: Clock, color: "#f97316" },
        ].map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: stat.color + "20" }}>
                <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
              </div>
              <span className="text-gray-500" style={{ fontSize: 12 }}>{stat.label}</span>
            </div>
            <div className="text-gray-900" style={{ fontSize: 22, fontWeight: 700 }}>{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Cost Trend */}
      <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>Daily Cost Trend</h3>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={mockCostHistory}>
            <defs>
              <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="oklch(78.9% 0.154 211.53)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="oklch(78.9% 0.154 211.53)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }} />
            <Area type="monotone" dataKey="cost" stroke="oklch(78.9% 0.154 211.53)" fill="url(#costGrad)" name="Cost ($)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Session List */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h3 className="text-gray-900" style={{ fontWeight: 600 }}>Sessions</h3>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            {["all", "active", "idle", "closed"].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-2 py-1 rounded-lg capitalize ${
                  statusFilter === s ? "text-white" : "text-gray-500 hover:bg-gray-100"
                }`}
                style={statusFilter === s ? { background: "var(--brand-gradient)", fontSize: 12 } : { fontSize: 12 }}
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
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Session ID</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Model</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Queries</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Cost</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Status</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Created</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((session) => (
                <tr
                  key={session.session_id}
                  className={`border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors ${
                    selectedSession === session.session_id ? "bg-brand-light/10" : ""
                  }`}
                  onClick={() => setSelectedSession(selectedSession === session.session_id ? null : session.session_id)}
                >
                  <td className="px-5 py-3">
                    <code className="text-brand-dark bg-brand-light/10 px-1.5 py-0.5 rounded" style={{ fontSize: 12 }}>
                      {session.session_id}
                    </code>
                  </td>
                  <td className="px-5 py-3 text-gray-600" style={{ fontSize: 13 }}>
                    {session.model.split("/")[1]}
                  </td>
                  <td className="px-5 py-3 text-gray-900" style={{ fontSize: 13, fontWeight: 500 }}>
                    {session.queries}
                  </td>
                  <td className="px-5 py-3 text-gray-900" style={{ fontSize: 13, fontWeight: 600 }}>
                    ${session.total_cost.toFixed(2)}
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full ${
                        session.status === "active" ? "bg-green-100 text-green-700" :
                        session.status === "idle" ? "bg-yellow-100 text-yellow-700" :
                        "bg-gray-100 text-gray-600"
                      }`}
                      style={{ fontSize: 11, fontWeight: 500 }}
                    >
                      {session.status}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-500" style={{ fontSize: 12 }}>
                    {new Date(session.created_at).toLocaleString()}
                  </td>
                  <td className="px-5 py-3">
                    <button className="w-7 h-7 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-400 hover:text-red-500">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Per-Session Detail */}
      {selectedSession && (
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>
            Cost History: <code className="text-brand-dark">{selectedSession}</code>
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={sessionCostHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Bar dataKey="cost" fill="oklch(78.9% 0.154 211.53)" radius={[4, 4, 0, 0]} name="Cost ($)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
