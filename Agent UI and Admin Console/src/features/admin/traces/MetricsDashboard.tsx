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
                <div className="rounded-lg border border-border bg-card p-4 sm:p-6 flex flex-col h-[400px]">
                    <h3 className="text-sm font-medium tracking-tight text-foreground mb-6 flex items-center gap-2">
                        <Activity className="size-4 text-primary" />
                        Global Evaluation Pass Rates
                    </h3>
                    <div className="flex-1 min-h-0">
                        {loading ? <Skeleton className="w-full h-full" /> : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="2 4" horizontal vertical={false} stroke="var(--border)" />
                                    <XAxis type="number" domain={[0, 100]} tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }} axisLine={false} tickLine={false} />
                                    <YAxis type="category" dataKey="name" tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }} axisLine={false} tickLine={false} width={120} />
                                    <Tooltip
                                        cursor={{ fill: 'var(--accent)' }}
                                        contentStyle={{ borderRadius: 6, border: '1px solid var(--border)', backgroundColor: 'var(--card)', color: 'var(--foreground)', fontSize: 12 }}
                                        formatter={(value: number) => [`${value}%`, 'Pass Rate']}
                                    />
                                    <Bar dataKey="passRate" radius={[0, 3, 3, 0]}>
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
                <div className="rounded-lg border border-border bg-card p-6 flex flex-col h-[400px] overflow-hidden">
                    <h3 className="text-sm font-medium tracking-tight text-foreground mb-6 flex items-center gap-2">
                        <CheckCircle2 className="size-4 text-[var(--success)]" />
                        Metric Details
                    </h3>
                    <div className="flex-1 overflow-y-auto pr-2">
                        {loading ? <Skeleton className="w-full h-full" /> : (
                            <div className="space-y-3">
                                {(summary || []).map((item, idx) => (
                                    <div key={item.metric_name} className="flex items-center justify-between p-3 rounded-md border border-border bg-muted/30">
                                        <div>
                                            <div className="font-medium text-foreground flex items-center gap-2">
                                                <div className="size-2 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                                                {item.metric_name}
                                            </div>
                                            <div className="text-xs text-muted-foreground mt-0.5 font-tabular">
                                                Evaluated <span className="text-foreground">{item.count}</span> times
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <div className="font-tabular text-foreground">{(item.pass_rate * 100).toFixed(1)}%</div>
                                            <div className="text-[10px] text-muted-foreground font-tabular uppercase tracking-[0.15em]">Pass Rate</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Failures Table */}
            <div className="rounded-lg border border-border bg-card overflow-hidden">
                <div className="px-6 py-4 border-b border-border bg-destructive/5 flex items-center gap-2">
                    <ShieldAlert className="size-4 text-destructive" />
                    <h3 className="text-sm font-medium tracking-tight text-foreground">Recent Evaluation Failures</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-muted/40">
                            <tr className="border-b border-border">
                                <th className="px-6 py-3 text-left text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">Trace ID</th>
                                <th className="px-6 py-3 text-left text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">Metric</th>
                                <th className="px-6 py-3 text-left text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">Score</th>
                                <th className="hidden md:table-cell px-6 py-3 text-left text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">Reasoning</th>
                                <th className="px-6 py-3 text-left text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">Time</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                            {loading ? (
                                Array.from({ length: 5 }).map((_, i) => (
                                    <tr key={i}>
                                        <td colSpan={5} className="p-4"><Skeleton className="h-8 w-full" /></td>
                                    </tr>
                                ))
                            ) : failures && failures.length > 0 ? (
                                failures.map((f, i) => (
                                    <tr key={`${f.trace_id}-${f.metric_name}-${i}`} className="hover:bg-accent/40 transition-colors">
                                        <td className="px-6 py-3 font-tabular text-xs text-primary">
                                            {buildTraceHref(f.trace_id) ? (
                                                <a href={buildTraceHref(f.trace_id)!} className="hover:underline">
                                                    {f.trace_id.split('-')[0]}...
                                                </a>
                                            ) : (
                                                <span>{f.trace_id.split('-')[0]}...</span>
                                            )}
                                        </td>
                                        <td className="px-6 py-3 text-foreground">{f.metric_name}</td>
                                        <td className="px-6 py-3">
                                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] bg-destructive/10 text-destructive font-tabular">
                                                {f.score.toFixed(1)}
                                            </span>
                                        </td>
                                        <td className="hidden md:table-cell px-6 py-3 text-xs text-muted-foreground max-w-md truncate" title={f.reasoning}>
                                            {f.reasoning || 'No justification provided'}
                                        </td>
                                        <td className="px-6 py-3 text-xs font-tabular text-muted-foreground">
                                            {f.updated_at ? formatDateTime(f.updated_at) : '—'}
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={5} className="px-6 py-12 text-center text-muted-foreground">
                                        <CheckCircle2 className="size-8 text-[var(--success)] mx-auto mb-2" />
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
