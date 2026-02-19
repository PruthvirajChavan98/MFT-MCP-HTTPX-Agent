import { useQuery } from '@tanstack/react-query'
import { Heart, CheckCircle, XCircle, RefreshCw, Server, Database, Globe, Network } from "lucide-react";
import { fetchSystemHealth } from '../../../shared/api/admin';
import { Skeleton } from '../ui/skeleton';
import { Alert, AlertDescription } from '../ui/alert';
import { cn } from '../ui/utils';

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

    if (error) return <Alert variant="destructive"><AlertDescription>{(error as Error).message}</AlertDescription></Alert>;

    return (
        <div className="space-y-8 max-w-[1200px] mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl text-gray-900 tracking-tight" style={{ fontWeight: 700 }}>System Health</h1>
                    <p className="text-gray-500 text-sm mt-1">Platform telemetry and dependency readiness</p>
                </div>
                <button
                    onClick={() => refetch()}
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
                </>
            )}
        </div>
    );
}