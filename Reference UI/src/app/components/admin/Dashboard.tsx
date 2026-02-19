import {
  Activity, Users, DollarSign, MessageSquare, Shield, TrendingUp,
  Database, ThumbsUp, Clock, Zap
} from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell } from "recharts";
import { mockAnalyticsOverview, mockCostHistory, mockQuestionCategories } from "../../lib/api";

const statCards = [
  { label: "Total Sessions", value: "1,247", icon: Users, change: "+12.3%", color: "#4ade80" },
  { label: "Total Queries", value: "15,832", icon: MessageSquare, change: "+8.7%", color: "#60a5fa" },
  { label: "Total Cost", value: "$342.87", icon: DollarSign, change: "+5.1%", color: "#f59e0b" },
  { label: "Avg Response Time", value: "1.24s", icon: Clock, change: "-15.2%", color: "#a78bfa" },
  { label: "FAQ Count", value: "256", icon: Database, change: "+18", color: "#34d399" },
  { label: "Satisfaction", value: "87.3%", icon: ThumbsUp, change: "+2.1%", color: "#f472b6" },
  { label: "Active Sessions", value: "38", icon: Zap, change: "live", color: "#fb923c" },
  { label: "Guardrail Triggers", value: "89", icon: Shield, change: "-3.4%", color: "#ef4444" },
];

const PIE_COLORS = ["#5eead4", "#67e8f9", "#38bdf8", "#818cf8", "#c084fc", "#f472b6", "#fb923c", "#fbbf24", "#a3e635"];

export function Dashboard() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-gray-900" style={{ fontWeight: 700 }}>Dashboard</h1>
        <p className="text-gray-500" style={{ fontSize: 14 }}>HFCL Agent Service analytics overview</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center"
                style={{ backgroundColor: stat.color + "20" }}
              >
                <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
              </div>
              <span
                className={`px-2 py-0.5 rounded-full ${
                  stat.change.startsWith("-") ? "bg-green-50 text-green-600" :
                  stat.change === "live" ? "bg-orange-50 text-orange-600" :
                  "bg-blue-50 text-blue-600"
                }`}
                style={{ fontSize: 11, fontWeight: 500 }}
              >
                {stat.change}
              </span>
            </div>
            <div className="text-gray-900" style={{ fontSize: 22, fontWeight: 700 }}>{stat.value}</div>
            <div className="text-gray-500" style={{ fontSize: 12 }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Cost & Query Trend */}
        <div className="lg:col-span-2 bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>Cost & Query Trend (7 Days)</h3>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={mockCostHistory}>
              <defs>
                <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="oklch(78.9% 0.154 211.53)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="oklch(78.9% 0.154 211.53)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
              <YAxis yAxisId="cost" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="queries" orientation="right" tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }} />
              <Area yAxisId="cost" type="monotone" dataKey="cost" stroke="oklch(78.9% 0.154 211.53)" fill="url(#colorCost)" name="Cost ($)" />
              <Bar yAxisId="queries" dataKey="queries" fill="oklch(85.5% 0.138 181.071)" opacity={0.6} name="Queries" barSize={20} radius={[4, 4, 0, 0]} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Question Categories Pie */}
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>Question Categories</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={mockQuestionCategories.slice(0, 6)}
                dataKey="count"
                nameKey="category"
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={2}
              >
                {mockQuestionCategories.slice(0, 6).map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-2">
            {mockQuestionCategories.slice(0, 5).map((cat, i) => (
              <div key={cat.category} className="flex items-center justify-between" style={{ fontSize: 12 }}>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: PIE_COLORS[i] }} />
                  <span className="text-gray-600">{cat.category}</span>
                </div>
                <span className="text-gray-900" style={{ fontWeight: 500 }}>{cat.percentage}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>Recent Activity</h3>
        <div className="space-y-3">
          {[
            { time: "2 min ago", event: "New query from sess_a1b2c3", type: "query", detail: "What are the foreclosure charges?" },
            { time: "5 min ago", event: "Guardrail triggered for sess_d4e5f6", type: "guardrail", detail: "Off-topic detection blocked" },
            { time: "12 min ago", event: "FAQ updated by admin", type: "admin", detail: "Updated: What is the processing fee?" },
            { time: "18 min ago", event: "New session created", type: "session", detail: "sess_g7h8i9 using deepseek-r1" },
            { time: "25 min ago", event: "Positive feedback received", type: "feedback", detail: "sess_j0k1l2: Great comparison!" },
          ].map((item) => (
            <div key={item.time} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors">
              <div className={`w-2 h-2 rounded-full mt-2 shrink-0 ${
                item.type === "query" ? "bg-blue-400" :
                item.type === "guardrail" ? "bg-red-400" :
                item.type === "admin" ? "bg-purple-400" :
                item.type === "session" ? "bg-green-400" :
                "bg-yellow-400"
              }`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-gray-900" style={{ fontSize: 13, fontWeight: 500 }}>{item.event}</span>
                  <span className="text-gray-400 shrink-0" style={{ fontSize: 11 }}>{item.time}</span>
                </div>
                <p className="text-gray-500 truncate" style={{ fontSize: 12 }}>{item.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
