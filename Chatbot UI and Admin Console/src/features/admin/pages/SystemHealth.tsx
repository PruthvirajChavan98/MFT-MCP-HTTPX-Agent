import { useQuery } from '@tanstack/react-query'
import { Heart, CheckCircle, XCircle, RefreshCw, Server, Database, Globe, Network, Shield, Activity } from "lucide-react";
import { fetchSystemHealth, fetchRateLimitMetrics, fetchRateLimitConfig } from '@features/admin/api/admin';
import { Skeleton } from '@components/ui/skeleton';
import { Alert, AlertDescription } from '@components/ui/alert';
import { cn } from '@components/ui/utils';

const DEPENDENCY_ICONS: Record<string, any> = {
    redis: Database,
    postgres: Server,
    tor_exit_list: Network,
};

export function SystemHealth() {
    const { data: health, isLoading, error, refetch, isFetching } = useQuery({
        queryKey: ['system-health'],
        queryFn: fetchSystemHealth,
        refetchInterval: 15000,
    });

    const { data: rlMetrics, isLoading: rlmLoading, refetch: refetchMetrics } = useQuery({
        queryKey: ['rate-limit-metrics'],
        queryFn: fetchRateLimitMetrics,
        refetchInterval: 15000,
    });

    const { data: rlConfig, isLoading: rlcLoading, refetch: refetchConfig } = useQuery({
        queryKey: ['rate-limit-config'],
        queryFn: fetchRateLimitConfig,
        refetchInterval: 60000,
    });

    const handleRefetch = () => {
        refetch();
        refetchMetrics();
        refetchConfig();
    };

    if (error) return <Alert variant="destructive"><AlertDescription>{(error as Error).message}</AlertDescription></Alert>;

    return (
        <div className="space-y-8 max-w-[1200px] mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl text-gray-900 tracking-tight" style={{ fontWeight: 700 }}>System Health</h1>
                    <p className="text-gray-500 text-sm mt-1">Platform telemetry and dependency readiness</p>
                </div>
                <button
                    onClick={handleRefetch}
                    disabled={isFetching}
                    className="px-4 py-2 rounded-xl border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 font-semibold text-sm flex items-center gap-2 shadow-sm transition-all disabled:opacity-50"
                >
                    <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin text-cyan-600' : ''}`} /> Sync State
                </button>
            </div>

            {isLoading || !health ? (
                <Skeleton className="w-full h-48 rounded-2xl" />
            ) : (
                <>
                    <div
                        className={cn(
                            "rounded-3xl p-8 text-white relative overflow-hidden shadow-xl",
                            health.healthy
                                ? "bg-gradient-to-r from-cyan-500 to-teal-500"
                                : "bg-gradient-to-r from-red-500 to-red-700"
                        )}
                    >
                        <div className="absolute top-4 right-4 opacity-10">
                            <Heart className="w-48 h-48" />
                        </div>
                        <div className="relative z-10">
                            <div className="flex items-center gap-4 mb-4">
                                <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center border border-white/30 shadow-inner">
                                    {health.healthy ? <CheckCircle className="w-8 h-8" /> : <XCircle className="w-8 h-8" />}
                                </div>
                                <div>
                                    <div className="text-white/80 font-semibold tracking-wider uppercase text-xs mb-1">Fleet Status</div>
                                    <div className="text-4xl capitalize tracking-tight" style={{ fontWeight: 800 }}>{health.status}</div>
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-8 mt-8 p-4 bg-black/10 rounded-2xl border border-white/10 backdrop-blur-sm w-max">
                                <div>
                                    <div className="text-white/70 text-xs font-bold uppercase tracking-wider mb-1">Time</div>
                                    <div className="font-mono text-sm">{new Date(health.timestamp * 1000).toUTCString()}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div>
                        <h3 className="text-lg font-bold text-gray-900 mb-4">Infrastructure Dependencies</h3>
                        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
                            {Object.entries(health.checks || {}).map(([name, dep]) => {
                                const Icon = DEPENDENCY_ICONS[name] || Globe;
                                const isHealthy = dep.ok;

                                return (
                                    <div key={name} className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden">
                                        <div className={`absolute top-0 left-0 w-1 h-full ${isHealthy ? 'bg-emerald-400' : 'bg-red-500'}`} />
                                        <div className="flex items-start justify-between mb-4 pl-2">
                                            <div className="flex items-center gap-3">
                                                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${isHealthy ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-600'}`}>
                                                    <Icon className="w-5 h-5" />
                                                </div>
                                                <div className="text-gray-900 capitalize font-bold text-base tracking-tight">{name.replace(/_/g, ' ')}</div>
                                            </div>
                                        </div>

                                        <div className="space-y-2.5 pl-2 pt-2 border-t border-gray-50">
                                            <div className="flex items-center justify-between">
                                                <span className="text-gray-500 text-xs font-semibold uppercase tracking-wider">Status</span>
                                                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase ${isHealthy ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                                                    {isHealthy ? 'Operational' : 'Failing'}
                                                </span>
                                            </div>
                                            {/* Dynamically render extra attributes like pool_min, stale_seconds */}
                                            {Object.entries(dep).filter(([k]) => k !== 'ok').map(([k, v]) => (
                                                <div key={k} className="flex items-center justify-between">
                                                    <span className="text-gray-500 text-xs font-semibold uppercase tracking-wider">{k.replace(/_/g, ' ')}</span>
                                                    <span className="font-mono text-xs text-gray-900 font-bold bg-gray-100 px-2 py-0.5 rounded">{String(v)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Rate Limiting Section */}
                    <div className="pt-6 border-t border-gray-100">
                        <div className="flex items-center gap-3 mb-6">
                            <h3 className="text-lg font-bold text-gray-900">Traffic & Rate Limiting</h3>
                            {rlConfig && (
                                <span className={cn("px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase",
                                    rlConfig.enabled ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700")}>
                                    {rlConfig.enabled ? 'Enforcing' : 'Disabled'}
                                </span>
                            )}
                        </div>

                        <div className="grid lg:grid-cols-2 gap-6">
                            {/* Global Config Card */}
                            <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm relative overflow-hidden">
                                <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
                                    <Shield className="w-32 h-32" />
                                </div>
                                <h4 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-4 flex items-center gap-2">
                                    <Shield className="w-4 h-4 text-cyan-500" /> Active Configuration
                                </h4>
                                {rlcLoading || !rlConfig ? <Skeleton className="w-full h-32" /> : (
                                    <div className="space-y-4">
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                                                <div className="text-slate-500 text-[10px] font-bold uppercase tracking-wider mb-1">Algorithm</div>
                                                <div className="text-slate-900 font-mono text-xs font-semibold">{rlConfig.algorithm}</div>
                                            </div>
                                            <div className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                                                <div className="text-slate-500 text-[10px] font-bold uppercase tracking-wider mb-1">Failure Mode</div>
                                                <div className="text-slate-900 font-mono text-xs font-semibold">{rlConfig.failure_mode}</div>
                                            </div>
                                            <div className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                                                <div className="text-slate-500 text-[10px] font-bold uppercase tracking-wider mb-1">Max Burst</div>
                                                <div className="text-slate-900 font-mono text-xs font-semibold">{rlConfig.max_burst} reqs</div>
                                            </div>
                                            <div className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                                                <div className="text-slate-500 text-[10px] font-bold uppercase tracking-wider mb-1">Per-IP Defense</div>
                                                <div className="text-slate-900 font-mono text-xs font-semibold">{rlConfig.per_ip_enabled ? `Active (${rlConfig.per_ip?.limit})` : 'Inactive'}</div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Endpoint Metrics */}
                            <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm flex flex-col items-start gap-4 h-full relative overflow-hidden">
                                <h4 className="text-sm font-bold text-gray-900 uppercase tracking-wider flex items-center gap-2">
                                    <Activity className="w-4 h-4 text-rose-500" /> Endpoint Quotas
                                </h4>
                                {rlmLoading || !rlMetrics ? <Skeleton className="w-full h-32" /> : (
                                    <div className="w-full overflow-x-auto no-scrollbar">
                                        <table className="w-full text-xs text-left">
                                            <thead>
                                                <tr className="border-b border-gray-100 text-slate-500 uppercase tracking-wider font-bold">
                                                    <th className="pb-2">Endpoint</th>
                                                    <th className="pb-2 text-right">Allowed</th>
                                                    <th className="pb-2 text-right">Denied</th>
                                                    <th className="pb-2 text-right">RPM</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-50/50">
                                                {Object.entries(rlMetrics.metrics || {}).map(([ep, stats]: [string, any]) => {
                                                    const cleanName = ep.replace('endpoint:', '');
                                                    return (
                                                        <tr key={ep}>
                                                            <td className="py-2.5 font-medium text-slate-700">/{cleanName}</td>
                                                            <td className="py-2.5 text-right font-mono text-emerald-600">{stats.requests_allowed}</td>
                                                            <td className="py-2.5 text-right font-mono text-red-500">{stats.requests_denied}</td>
                                                            <td className="py-2.5 text-right font-mono text-slate-500">{stats.rate}</td>
                                                        </tr>
                                                    )
                                                })}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
