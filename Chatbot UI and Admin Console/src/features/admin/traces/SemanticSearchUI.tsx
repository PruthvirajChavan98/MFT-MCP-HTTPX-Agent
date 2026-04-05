import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, BrainCircuit, ExternalLink } from 'lucide-react';
import { fetchVectorSearch } from '@features/admin/api/admin';
import { useAdminContext } from '@features/admin/context/AdminContext';
import { Input } from '@components/ui/input';
import { Button } from '@components/ui/button';
import { Skeleton } from '@components/ui/skeleton';
import { formatDateTime } from '@shared/lib/format';
import { buildTraceHref } from '@features/admin/lib/admin-links';

export function SemanticSearchUI() {
    const auth = useAdminContext();
    const [query, setQuery] = useState('');
    const [activeQuery, setActiveQuery] = useState('');

    const { data, isLoading, error } = useQuery({
        queryKey: ['vector-search', auth.adminKey, activeQuery],
        queryFn: () => fetchVectorSearch({ adminKey: auth.adminKey, kind: 'trace', text: activeQuery, k: 5 }),
        enabled: activeQuery.length > 2,
    });

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        if (query.trim()) {
            setActiveQuery(query.trim());
        }
    };

    return (
        <div className="flex flex-col h-full sm:h-[500px]">
            <div className="mb-6">
                <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2 sm:gap-3">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <Input
                            placeholder="Search traces semantically (e.g. 'user asking about loan foreclosure')"
                            className="w-full pl-9 bg-white border-slate-200"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                        />
                    </div>
                    <Button type="submit" disabled={!query.trim() || isLoading} className="w-full sm:w-auto bg-cyan-600 hover:bg-cyan-700 text-white">
                        <BrainCircuit className="w-4 h-4 mr-2" /> Search Vectors
                    </Button>
                </form>
            </div>

            <div className="flex-1 overflow-y-auto pr-2">
                {error ? (
                    <div className="p-4 bg-rose-50 text-rose-700 rounded-xl border border-rose-100 text-sm">
                        {(error as Error).message}
                    </div>
                ) : isLoading && activeQuery ? (
                    <div className="space-y-3">
                        {Array.from({ length: 3 }).map((_, i) => (
                            <Skeleton key={i} className="w-full h-24 rounded-xl" />
                        ))}
                    </div>
                ) : !activeQuery ? (
                    <div className="flex flex-col items-center justify-center h-full text-slate-400">
                        <BrainCircuit className="w-12 h-12 mb-4 text-slate-200" />
                        <p>Enter a query to dive into the embedding space.</p>
                    </div>
                ) : data?.items?.length === 0 ? (
                    <div className="text-center py-10 text-slate-500">
                        No semantically similar traces found.
                    </div>
                ) : (
                    <div className="space-y-3">
                        {(data?.items || []).map((trace) => (
                            <div key={trace.trace_id} className="bg-white p-4 rounded-xl border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
                                <div className="flex items-start justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                        <span className="font-mono text-xs font-bold text-cyan-700 bg-cyan-50 px-2 py-0.5 rounded">
                                            {(trace.score * 100).toFixed(1)}% Match
                                        </span>
                                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider ${trace.status === 'success' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                                            {trace.status}
                                        </span>
                                    </div>
                                    {buildTraceHref(trace.trace_id) ? (
                                        <a
                                            href={buildTraceHref(trace.trace_id)!}
                                            className="text-xs font-medium text-indigo-600 flex items-center gap-1 hover:underline"
                                        >
                                            View Trace <ExternalLink className="w-3 h-3" />
                                        </a>
                                    ) : (
                                        <span className="text-xs font-medium text-slate-400">Trace unavailable</span>
                                    )}
                                </div>
                                <p className="text-sm font-semibold text-slate-800 line-clamp-2 mt-2">
                                    {trace.question || trace.event_key || 'Unknown Event'}
                                </p>
                                <div className="flex items-center gap-3 mt-3 text-xs font-medium text-slate-500">
                                    <span className="font-mono text-slate-400">{trace.trace_id.split('-')[0]}...</span>
                                    <span>•</span>
                                    <span>{trace.model?.split('/').pop() || 'Unknown Model'}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
