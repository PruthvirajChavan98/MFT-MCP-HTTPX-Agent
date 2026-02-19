import { useState } from "react";
import { Tag, TrendingUp, TrendingDown, BarChart3, PieChart as PieChartIcon, ArrowUpRight } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Treemap
} from "recharts";
import { mockQuestionCategories, mockTraces } from "../../lib/api";

const COLORS = ["#5eead4", "#67e8f9", "#38bdf8", "#818cf8", "#c084fc", "#f472b6", "#fb923c", "#fbbf24", "#a3e635"];

export function QuestionCategories() {
  const [view, setView] = useState<"bar" | "pie" | "tree">("bar");

  const totalQuestions = mockQuestionCategories.reduce((acc, c) => acc + c.count, 0);

  // Mock recent question examples per category
  const recentByCategory: Record<string, string[]> = {
    "Home Loans": ["What is the interest rate?", "Maximum loan amount?", "Can I get a top-up?"],
    "Personal Loans": ["What documents are needed?", "How fast is approval?", "Can I apply online?"],
    "EMI & Payments": ["How to change EMI date?", "Can I pay extra EMI?", "EMI calculator?"],
    "Fees & Charges": ["Foreclosure charges?", "Processing fee?", "Late payment penalty?"],
    "Account Services": ["How to check balance?", "Download statement?", "Update address?"],
    "Balance Transfer": ["Can I transfer from HDFC?", "What's the process?", "Any charges?"],
    "Property Loans": ["LAP eligibility?", "Property valuation?", "Loan to value ratio?"],
    "Off Topic / Blocked": ["Tell me a joke", "Political opinions", "Recipe for cake"],
    "General Inquiry": ["Branch locations?", "Customer care number?", "Working hours?"],
  };

  const treemapData = mockQuestionCategories.map((c, i) => ({
    name: c.category,
    size: c.count,
    fill: COLORS[i % COLORS.length],
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-gray-900" style={{ fontWeight: 700 }}>Question Categories</h1>
          <p className="text-gray-500" style={{ fontSize: 14 }}>
            Router classification analysis &middot; {totalQuestions.toLocaleString()} total questions
          </p>
        </div>
        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
          {[
            { key: "bar" as const, icon: BarChart3 },
            { key: "pie" as const, icon: PieChartIcon },
          ].map((v) => (
            <button
              key={v.key}
              onClick={() => setView(v.key)}
              className={`w-8 h-8 rounded-md flex items-center justify-center transition-all ${
                view === v.key ? "bg-white shadow-sm text-gray-900" : "text-gray-500"
              }`}
            >
              <v.icon className="w-4 h-4" />
            </button>
          ))}
        </div>
      </div>

      {/* Category Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {mockQuestionCategories.map((cat, i) => (
          <div key={cat.category} className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm hover:shadow-md transition-all">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                <span className="text-gray-900" style={{ fontSize: 13, fontWeight: 600 }}>{cat.category}</span>
              </div>
              <span
                className={`flex items-center gap-0.5 ${
                  cat.trend.startsWith("+") ? "text-green-600" : "text-red-500"
                }`}
                style={{ fontSize: 11, fontWeight: 500 }}
              >
                {cat.trend.startsWith("+") ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {cat.trend}
              </span>
            </div>
            <div className="text-gray-900 mb-1" style={{ fontSize: 24, fontWeight: 700 }}>
              {cat.count.toLocaleString()}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400" style={{ fontSize: 11 }}>{cat.percentage}% of total</span>
            </div>
            {/* Mini bar */}
            <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${cat.percentage}%`, backgroundColor: COLORS[i % COLORS.length] }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Chart */}
      <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>Distribution</h3>
        <ResponsiveContainer width="100%" height={320}>
          {view === "bar" ? (
            <BarChart data={mockQuestionCategories} layout="vertical" margin={{ left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="category" tick={{ fontSize: 11 }} width={120} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {mockQuestionCategories.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          ) : (
            <PieChart>
              <Pie
                data={mockQuestionCategories}
                dataKey="count"
                nameKey="category"
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={120}
                paddingAngle={2}
                label={({ category, percentage }) => `${category} (${percentage}%)`}
              >
                {mockQuestionCategories.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            </PieChart>
          )}
        </ResponsiveContainer>
      </div>

      {/* Recent Examples */}
      <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>Recent Question Examples</h3>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {mockQuestionCategories.slice(0, 6).map((cat, i) => (
            <div key={cat.category} className="rounded-lg border border-gray-100 p-3">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                <span className="text-gray-900" style={{ fontSize: 12, fontWeight: 600 }}>{cat.category}</span>
              </div>
              <div className="space-y-1.5">
                {(recentByCategory[cat.category] || []).map((q) => (
                  <div key={q} className="text-gray-600 flex items-start gap-1.5" style={{ fontSize: 12 }}>
                    <span className="text-gray-400 mt-0.5 shrink-0">&bull;</span>
                    <span>{q}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
