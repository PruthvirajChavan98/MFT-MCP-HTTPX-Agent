import { useQuery } from '@tanstack/react-query';
import { fetchMetricsSummary, fetchMetricFailures } from '@features/admin/api/admin';
import { Skeleton } from '@components/ui/skeleton';
import { Alert, AlertDescription } from '@components/ui/alert';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip, Cell } from 'recharts';
import { Activity, AlertTriangle, ShieldAlert, CheckCircle2, XCircle } from 'lucide-react';
import { formatDateTime } from '@shared/lib/format';
import { buildTraceHref } from '@features/admin/lib/admin-links';

const COLORS = ['#34d399', '#60a5fa', '#a78bfa', '#f472b6', '#fb923c', '#fbbf24', '#2dd4bf'];

export function MetricsDashboard() {
    const { data: summary, isLoading: sLoading, error: sError } = useQuery({
        queryKey: ['eval-metrics-summary'],
        queryFn: () => fetchMetricsSummary(),
        refetchInterval: 30000,
    });

    const { data: failures, isLoading: fLoading, error: fError } = useQuery({
        queryKey: ['eval-metrics-failures'],
        queryFn: () => fetchMetricFailures(100),
        refetchInterval: 30000,
    });

    const loading = sLoading || fLoading;
    const error = sError || fError;

    if (error) {
        return (
            <Alert variant="destructive">
                <AlertDescription>{(error as Error).message}</AlertDescription>
            </Alert>
        );
    }

    // Format data for the bar chart
    const chartData = (summary || []).map(item => ({
        name: item.metric_name,
        passRate: Math.round(item.pass_rate * 100),
        avgScore: Math.round(item.avg_score * 10) / 10,
        count: item.count,
    }));

    return (
        <div className="space-y-6">
            <div className="grid xl:grid-cols-2 gap-6">
                {/* Pass Rates Chart */}
                <div className="bg-white rounded-xl p-4 sm:p-6 border border-gray-100 shadow-sm flex flex-col h-[400px]">
                    <h3 className="text-gray-900 mb-6 text-base font-bold flex items-center gap-2">
                        <Activity className="w-5 h-5 text-cyan-600" />
                        Global Evaluation Pass Rates
                    </h3>
                    <div className="flex-1 min-h-0">
                        {loading ? <Skeleton className="w-full h-full" /> : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="#f1f5f9" />
                                    <XAxis type="number" domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 12 }} />
                                    <YAxis type="category" dataKey="name" tick={{ fill: '#64748b', fontSize: 12 }} width={120} />
                                    <Tooltip
                                        cursor={{ fill: 'transparent' }}
                                        contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                                        formatter={(value: number) => [`${value}%`, 'Pass Rate']}
                                    />
                                    <Bar dataKey="passRate" radius={[0, 4, 4, 0]}>
                                        {chartData.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>

                {/* Aggregate Stats */}
                <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm flex flex-col h-[400px] overflow-hidden">
                    <h3 className="text-gray-900 mb-6 text-base font-bold flex items-center gap-2">
                        <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                        Metric Details
                    </h3>
                    <div className="flex-1 overflow-y-auto pr-2">
                        {loading ? <Skeleton className="w-full h-full" /> : (
                            <div className="space-y-3">
                                {(summary || []).map((item, idx) => (
                                    <div key={item.metric_name} className="flex items-center justify-between p-3 rounded-lg border border-slate-100 bg-slate-50/50">
                                        <div>
                                            <div className="font-bold text-slate-800 flex items-center gap-2">
                                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                                                {item.metric_name}
                                            </div>
                                            <div className="text-xs text-slate-500 mt-0.5">Evaluated {item.count} times</div>
                                        </div>
                                        <div className="text-right">
                                            <div className="font-mono font-bold text-slate-900">{(item.pass_rate * 100).toFixed(1)}%</div>
                                            <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Pass Rate</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Failures Table */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                <div className="px-6 py-5 border-b border-gray-100 bg-rose-50/30 flex items-center gap-2">
                    <ShieldAlert className="w-5 h-5 text-rose-500" />
                    <h3 className="text-gray-900 text-base font-bold">Recent Evaluation Failures</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50/50">
                            <tr className="border-b border-gray-100">
                                <th className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">Trace ID</th>
                                <th className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">Metric</th>
                                <th className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">Score</th>
                                <th className="hidden md:table-cell px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">Reasoning</th>
                                <th className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">Time</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                            {loading ? (
                                Array.from({ length: 5 }).map((_, i) => (
                                    <tr key={i}>
                                        <td colSpan={5} className="p-4"><Skeleton className="h-8 w-full" /></td>
                                    </tr>
                                ))
                            ) : failures && failures.length > 0 ? (
                                failures.map((f, i) => (
                                    <tr key={`${f.trace_id}-${f.metric_name}-${i}`} className="hover:bg-slate-50/80 transition-colors">
                                        <td className="px-6 py-4 font-mono text-xs text-indigo-600 font-medium">
                                            {buildTraceHref(f.trace_id) ? (
                                                <a href={buildTraceHref(f.trace_id)!} className="hover:underline">
                                                    {f.trace_id.split('-')[0]}...
                                                </a>
                                            ) : (
                                                <span>{f.trace_id.split('-')[0]}...</span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 font-bold text-slate-700">{f.metric_name}</td>
                                        <td className="px-6 py-4">
                                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-rose-100 text-rose-700 font-mono">
                                                {f.score.toFixed(1)}
                                            </span>
                                        </td>
                                        <td className="hidden md:table-cell px-6 py-4 text-xs text-slate-600 max-w-md truncate" title={f.reasoning}>
                                            {f.reasoning || 'No justification provided'}
                                        </td>
                                        <td className="px-6 py-4 text-xs text-slate-500">
                                            {f.updated_at ? formatDateTime(f.updated_at) : '—'}
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={5} className="px-6 py-12 text-center text-slate-500">
                                        <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                                        <p>No recent evaluation failures found.</p>
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
