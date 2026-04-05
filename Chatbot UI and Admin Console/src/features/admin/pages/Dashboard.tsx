import { useMemo } from "react";
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { Activity, Users, DollarSign, MessageSquare, Shield, Clock } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { fetchEvalTraces, fetchSessionCostSummary, fetchQuestionTypes, fetchGuardrailEvents } from '@features/admin/api/admin';
import { useAdminContext } from '@features/admin/context/AdminContext';
import { Skeleton } from '@components/ui/skeleton';
import { Alert, AlertDescription } from '@components/ui/alert';
import { ResponsiveGrid } from '@components/ui/responsive-grid';
import { ResponsiveTable, type Column } from '@components/ui/responsive-table';
import { MobileHeader } from '@components/ui/mobile-header';
import { formatCurrency, formatDateTime } from '@shared/lib/format';
import { buildConversationHref, buildTraceHref } from '@features/admin/lib/admin-links';
import type { EvalTraceSummary } from '@features/admin/types/admin';

const PIE_COLORS = ["#5eead4", "#67e8f9", "#38bdf8", "#818cf8", "#c084fc", "#f472b6", "#fb923c", "#fbbf24", "#a3e635"];

const dashboardTraceColumns: Column<EvalTraceSummary>[] = [
  { key: 'status', label: 'Status' },
  { key: 'trace_id', label: 'Trace ID' },
  { key: 'model', label: 'Model', visibleFrom: 'md' },
  { key: 'latency_ms', label: 'Latency', visibleFrom: 'md' },
  { key: 'started_at', label: 'Started' },
  { key: 'action', label: 'Action' },
];

function renderDashboardTraceCell(t: EvalTraceSummary, column: Column<EvalTraceSummary>) {
  switch (column.key) {
    case 'status':
      return (
        <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold tracking-wide uppercase ${t.status === 'success' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
          {t.status}
        </span>
      );
    case 'trace_id':
      return <span className="font-mono text-xs text-slate-600 font-medium truncate max-w-30">{t.trace_id}</span>;
    case 'model':
      return <span className="text-slate-700 font-medium">{t.model?.split('/').pop() ?? '\u2014'}</span>;
    case 'latency_ms':
      return <span className="text-slate-700 font-mono">{t.latency_ms ? `${t.latency_ms}ms` : '\u2014'}</span>;
    case 'started_at':
      return <span className="text-slate-500">{formatDateTime(t.started_at)}</span>;
    case 'action':
      return (
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-1.5">
          {buildConversationHref(t.session_id) ? (
            <Link
              to={buildConversationHref(t.session_id)!}
              className="inline-flex items-center rounded-md border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-xs font-semibold text-cyan-700 transition hover:bg-cyan-100"
            >
              View Conversation
            </Link>
          ) : (
            <span className="text-xs text-slate-400">No session</span>
          )}
          {buildTraceHref(t.trace_id) && (
            <Link
              to={buildTraceHref(t.trace_id)!}
              className="inline-flex items-center rounded-md border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 transition hover:bg-indigo-100"
            >
              Inspect Trace
            </Link>
          )}
        </div>
      );
    default:
      return null;
  }
}

export function Dashboard() {
  const auth = useAdminContext();

  const { data: traces = [], isLoading: tLoading, error: tError } = useQuery({
    queryKey: ['eval-traces', auth.adminKey],
    queryFn: () => fetchEvalTraces(auth.adminKey, 200),
    refetchInterval: 30_000,
  });

  const { data: costs, isLoading: cLoading, error: cError } = useQuery({
    queryKey: ['session-cost-summary'],
    queryFn: fetchSessionCostSummary,
    refetchInterval: 30_000,
  });

  const { data: categories = [], isLoading: catLoading } = useQuery({
    queryKey: ['question-types', auth.adminKey],
    queryFn: () => fetchQuestionTypes(auth.adminKey, 50),
  });

  const { data: guardrails = [] } = useQuery({
    queryKey: ['guardrail-events', auth.adminKey],
    queryFn: async () => (await fetchGuardrailEvents(auth.adminKey, { limit: 100 })).items,
  });

  const loading = tLoading || cLoading || catLoading;
  const error = tError || cError;

  // Process data for charts
  const activityTrend = useMemo(() => {
    if (!traces.length) return [];
    const counts: Record<string, number> = {};
    traces.forEach(t => {
      if (!t.started_at) return;
      const date = new Date(t.started_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      counts[date] = (counts[date] || 0) + 1;
    });
    return Object.entries(counts).map(([date, count]) => ({ date, requests: count })).reverse(); // oldest to newest
  }, [traces]);

  const successCount = traces.filter((t) => t.status === 'success' || !t.error).length;
  const successRate = traces.length ? ((successCount / traces.length) * 100).toFixed(1) : 0;
  const avgLatency = traces.length ? Math.round(traces.reduce((s, t) => s + (t.latency_ms ?? 0), 0) / traces.length) : 0;

  if (error) return <Alert variant="destructive"><AlertDescription className="font-mono text-xs">{(error as Error).message}</AlertDescription></Alert>;

  const statCards = [
    { label: "Active Sessions", value: costs?.active_sessions?.toLocaleString() || "0", icon: Users, color: "#4ade80" },
    { label: "Total Queries", value: traces.length.toLocaleString(), icon: MessageSquare, color: "#60a5fa" },
    { label: "Total Cost", value: formatCurrency(costs?.total_cost ?? 0), icon: DollarSign, color: "#f59e0b" },
    { label: "Avg Latency", value: `${avgLatency}ms`, icon: Clock, color: "#a78bfa" },
    { label: "Success Rate", value: `${successRate}%`, icon: Activity, color: "#34d399" },
    { label: "Guardrail Blocks", value: guardrails.filter(g => g.risk_decision === 'deny').length.toString(), icon: Shield, color: "#ef4444" },
  ];

  return (
    <div className="space-y-6 max-w-[1600px] mx-auto">
      <MobileHeader
        title="Overview"
        description="Real-time metrics from the Mock FinTech Agent Service"
      />

      {/* KPIs */}
      <ResponsiveGrid cols={{ base: 2, lg: 3, xl: 6 }}>
        {loading ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />) : statCards.map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between mb-4">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: stat.color + "20" }}>
                <stat.icon className="w-5 h-5" style={{ color: stat.color }} />
              </div>
            </div>
            <div className="text-gray-900" style={{ fontSize: 24, fontWeight: 800 }}>{stat.value}</div>
            <div className="text-gray-500 font-medium tracking-wide mt-1" style={{ fontSize: 11, textTransform: 'uppercase' }}>{stat.label}</div>
          </div>
        ))}
      </ResponsiveGrid>

      <div className="grid xl:grid-cols-3 gap-6">
        {/* Activity Chart */}
        <div className="xl:col-span-2 bg-white rounded-xl p-6 border border-gray-100 shadow-sm flex flex-col">
          <h3 className="text-gray-900 mb-6 text-base" style={{ fontWeight: 700 }}>Request Volume Trend</h3>
          <div className="flex-1 min-h-[300px]">
            {loading ? <Skeleton className="h-full w-full rounded-lg" /> : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={activityTrend}>
                  <defs>
                    <linearGradient id="colorReq" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="oklch(78.9% 0.154 211.53)" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="oklch(78.9% 0.154 211.53)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} dy={10} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} dx={-10} />
                  <Tooltip
                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                    itemStyle={{ color: '#0f172a', fontWeight: 600 }}
                  />
                  <Area type="monotone" dataKey="requests" stroke="oklch(78.9% 0.154 211.53)" strokeWidth={3} fill="url(#colorReq)" name="Requests" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Router Categories */}
        <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm flex flex-col">
          <h3 className="text-gray-900 mb-6 text-base" style={{ fontWeight: 700 }}>Topic Distribution</h3>
          <div className="flex-1 min-h-[220px]">
            {loading ? <Skeleton className="h-full w-full rounded-lg" /> : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={categories.slice(0, 6)}
                    dataKey="count"
                    nameKey="reason"
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={3}
                  >
                    {categories.slice(0, 6).map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="space-y-2.5 mt-4">
            {categories.slice(0, 4).map((cat, i) => (
              <div key={cat.reason} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  <span className="w-3 h-3 rounded-full shadow-inner" style={{ backgroundColor: PIE_COLORS[i] }} />
                  <span className="text-slate-600 font-medium truncate max-w-[150px]">{cat.reason.replace(/_/g, ' ')}</span>
                </div>
                <span className="text-slate-900 font-bold font-mono">{(cat.pct * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Traces Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-100 bg-slate-50/50 flex justify-between items-center">
          <h3 className="text-gray-900 text-base" style={{ fontWeight: 700 }}>Recent Executions</h3>
        </div>
        {loading ? (
          <div className="divide-y divide-gray-50">
            {Array.from({ length: 5 }).map((_, i) => <div key={i} className="p-4"><Skeleton className="h-8 w-full" /></div>)}
          </div>
        ) : (
          <ResponsiveTable<EvalTraceSummary>
            columns={dashboardTraceColumns}
            data={traces.slice(0, 8)}
            renderCell={renderDashboardTraceCell}
          />
        )}
      </div>
    </div>
  );
}
