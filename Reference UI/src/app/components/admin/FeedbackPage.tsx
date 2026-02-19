import { useState } from "react";
import { ThumbsUp, ThumbsDown, MessageSquare, Filter, TrendingUp, Star } from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";
import { mockFeedback } from "../../lib/api";

const CATEGORY_COLORS: Record<string, string> = {
  accuracy: "#34d399",
  relevance: "#60a5fa",
  completeness: "#818cf8",
  speed: "#f59e0b",
  clarity: "#f472b6",
};

export function FeedbackPage() {
  const [feedback] = useState(mockFeedback);
  const [filter, setFilter] = useState<"all" | "thumbs_up" | "thumbs_down">("all");

  const filtered = feedback.filter((f) => filter === "all" || f.rating === filter);
  const thumbsUp = feedback.filter((f) => f.rating === "thumbs_up").length;
  const thumbsDown = feedback.filter((f) => f.rating === "thumbs_down").length;
  const satisfactionRate = ((thumbsUp / feedback.length) * 100).toFixed(1);

  const categoryData = Object.entries(
    feedback.reduce<Record<string, number>>((acc, f) => {
      acc[f.category] = (acc[f.category] || 0) + 1;
      return acc;
    }, {})
  ).map(([name, value]) => ({ name, value }));

  const ratingTrend = [
    { day: "Mon", positive: 45, negative: 8 },
    { day: "Tue", positive: 52, negative: 6 },
    { day: "Wed", positive: 38, negative: 12 },
    { day: "Thu", positive: 61, negative: 5 },
    { day: "Fri", positive: 47, negative: 9 },
    { day: "Sat", positive: 33, negative: 4 },
    { day: "Sun", positive: 28, negative: 3 },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-gray-900" style={{ fontWeight: 700 }}>Feedback</h1>
        <p className="text-gray-500" style={{ fontSize: 14 }}>User satisfaction tracking & analysis</p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-green-100 flex items-center justify-center">
              <ThumbsUp className="w-4 h-4 text-green-600" />
            </div>
            <span className="text-gray-500" style={{ fontSize: 12 }}>Positive</span>
          </div>
          <div className="text-gray-900" style={{ fontSize: 24, fontWeight: 700 }}>{thumbsUp}</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-red-100 flex items-center justify-center">
              <ThumbsDown className="w-4 h-4 text-red-500" />
            </div>
            <span className="text-gray-500" style={{ fontSize: 12 }}>Negative</span>
          </div>
          <div className="text-gray-900" style={{ fontSize: 24, fontWeight: 700 }}>{thumbsDown}</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-yellow-100 flex items-center justify-center">
              <Star className="w-4 h-4 text-yellow-600" />
            </div>
            <span className="text-gray-500" style={{ fontSize: 12 }}>Satisfaction</span>
          </div>
          <div className="text-gray-900" style={{ fontSize: 24, fontWeight: 700 }}>{satisfactionRate}%</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
              <MessageSquare className="w-4 h-4 text-blue-600" />
            </div>
            <span className="text-gray-500" style={{ fontSize: 12 }}>Total Feedback</span>
          </div>
          <div className="text-gray-900" style={{ fontSize: 24, fontWeight: 700 }}>{feedback.length}</div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>Rating Trend (This Week)</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={ratingTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Bar dataKey="positive" fill="#34d399" stackId="a" radius={[0, 0, 0, 0]} name="Positive" />
              <Bar dataKey="negative" fill="#f87171" stackId="a" radius={[4, 4, 0, 0]} name="Negative" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>Feedback by Category</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={categoryData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3}>
                {categoryData.map((entry) => (
                  <Cell key={entry.name} fill={CATEGORY_COLORS[entry.name] || "#9ca3af"} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-3 mt-2 justify-center">
            {categoryData.map((cat) => (
              <div key={cat.name} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: CATEGORY_COLORS[cat.name] || "#9ca3af" }} />
                <span className="text-gray-600 capitalize" style={{ fontSize: 11 }}>{cat.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Feedback List */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h3 className="text-gray-900" style={{ fontWeight: 600 }}>Recent Feedback</h3>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            {(["all", "thumbs_up", "thumbs_down"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-2 py-1 rounded-lg ${
                  filter === f ? "text-white" : "text-gray-500 bg-gray-100 hover:bg-gray-200"
                }`}
                style={filter === f ? { background: "var(--brand-gradient)", fontSize: 12 } : { fontSize: 12 }}
              >
                {f === "all" ? "All" : f === "thumbs_up" ? "Positive" : "Negative"}
              </button>
            ))}
          </div>
        </div>

        <div className="divide-y divide-gray-50">
          {filtered.map((fb) => (
            <div key={fb.id} className="px-5 py-3 hover:bg-gray-50 transition-colors">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  {fb.rating === "thumbs_up" ? (
                    <ThumbsUp className="w-4 h-4 text-green-500" />
                  ) : (
                    <ThumbsDown className="w-4 h-4 text-red-500" />
                  )}
                  <code className="text-brand-dark" style={{ fontSize: 11 }}>{fb.session_id}</code>
                  <span
                    className="px-2 py-0.5 rounded-full capitalize"
                    style={{
                      fontSize: 10,
                      fontWeight: 500,
                      backgroundColor: (CATEGORY_COLORS[fb.category] || "#9ca3af") + "20",
                      color: CATEGORY_COLORS[fb.category] || "#6b7280",
                    }}
                  >
                    {fb.category}
                  </span>
                </div>
                <span className="text-gray-400" style={{ fontSize: 11 }}>
                  {new Date(fb.timestamp).toLocaleString()}
                </span>
              </div>
              {fb.comment && (
                <p className="text-gray-600 ml-6" style={{ fontSize: 13 }}>{fb.comment}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
