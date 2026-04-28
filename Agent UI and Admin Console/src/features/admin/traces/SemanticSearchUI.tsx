import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, BrainCircuit, ExternalLink } from 'lucide-react';
import { fetchVectorSearch } from '@features/admin/api/admin';
import { Input } from '@components/ui/input';
import { Button } from '@components/ui/button';
import { Skeleton } from '@components/ui/skeleton';
import { formatDateTime } from '@shared/lib/format';
import { buildTraceHref } from '@features/admin/lib/admin-links';

export function SemanticSearchUI() {
    const [query, setQuery] = useState('');
    const [activeQuery, setActiveQuery] = useState('');

    // `staleTime: 0` + `gcTime: 0` defeat the default 5-minute TanStack
    // cache for this explicit-action surface. The operator pressing
    // "Search Vectors" is asking the backend to re-run the similarity
    // search, so we want every submit to fetch afresh — not a stale
    // copy from the in-memory cache.
    const vectorSearch = useQuery({
        queryKey: ['vector-search', activeQuery],
        queryFn: () => fetchVectorSearch({ kind: 'trace', text: activeQuery, k: 5 }),
        enabled: activeQuery.length > 2,
        staleTime: 0,
        gcTime: 0,
    });
    const { data, error, isFetching } = vectorSearch;
    // Render the skeleton whenever a fetch is in flight (initial load OR
    // a refetch triggered by a same-text click). The previous `isLoading`
    // only covered the first-hit case.
    const isLoading = isFetching;

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        const trimmed = query.trim();
        if (!trimmed) return;
        if (trimmed === activeQuery) {
            // Same text as before — the queryKey wouldn't change so
            // TanStack would serve the cached result. Force a refetch so
            // the operator sees the backend's latest answer.
            vectorSearch.refetch();
        } else {
            setActiveQuery(trimmed);
        }
    };

    return (
        <div className="flex flex-col h-full sm:h-[500px]">
            <div className="mb-6">
                <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2 sm:gap-3">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                        <Input
                            placeholder="Search traces semantically (e.g. 'user asking about loan foreclosure')"
                            className="w-full pl-9 bg-card"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                        />
                    </div>
                    <Button type="submit" disabled={!query.trim() || isLoading} className="w-full sm:w-auto">
                        <BrainCircuit className="size-4 mr-2" /> Search Vectors
                    </Button>
                </form>
            </div>

            <div className="flex-1 overflow-y-auto pr-2">
                {error ? (
                    <div className="p-4 bg-destructive/10 text-destructive rounded-md border border-destructive/30 text-sm">
                        {(error as Error).message}
                    </div>
                ) : isLoading && activeQuery ? (
                    <div className="space-y-3">
                        {Array.from({ length: 3 }).map((_, i) => (
                            <Skeleton key={i} className="w-full h-24 rounded-md" />
                        ))}
                    </div>
                ) : !activeQuery ? (
                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                        <BrainCircuit className="size-12 mb-4 text-muted-foreground/40" />
                        <p className="text-sm">Enter a query to dive into the embedding space.</p>
                    </div>
                ) : data?.items?.length === 0 ? (
                    <div className="text-center py-10 text-muted-foreground text-sm">
                        No semantically similar traces found.
                    </div>
                ) : (
                    <div className="space-y-3">
                        {(data?.items || []).map((trace) => (
                            <div key={trace.trace_id} className="bg-card p-4 rounded-md border border-border transition-colors hover:bg-accent/30">
                                <div className="flex items-start justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                        <span className="font-tabular text-xs text-primary bg-primary/10 px-2 py-0.5 rounded">
                                            {(trace.score * 100).toFixed(1)}% Match
                                        </span>
                                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-tabular uppercase tracking-[0.15em] ${trace.status === 'success' ? 'bg-[var(--success-soft)] text-[var(--success)]' : 'bg-destructive/10 text-destructive'}`}>
                                            {trace.status}
                                        </span>
                                    </div>
                                    {buildTraceHref(trace.trace_id) ? (
                                        <a
                                            href={buildTraceHref(trace.trace_id)!}
                                            className="text-xs font-medium text-primary flex items-center gap-1 hover:underline"
                                        >
                                            View Trace <ExternalLink className="size-3" />
                                        </a>
                                    ) : (
                                        <span className="text-xs text-muted-foreground">Trace unavailable</span>
                                    )}
                                </div>
                                <p className="text-sm font-medium text-foreground line-clamp-2 mt-2">
                                    {trace.question || trace.event_key || 'Unknown Event'}
                                </p>
                                <div className="flex items-center gap-3 mt-3 text-xs text-muted-foreground">
                                    <span className="font-tabular">{trace.trace_id.split('-')[0]}...</span>
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
