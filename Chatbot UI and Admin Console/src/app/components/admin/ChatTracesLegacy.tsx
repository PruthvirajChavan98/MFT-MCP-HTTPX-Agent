import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { Search, CheckCircle2, XCircle, ExternalLink, MessageSquare } from 'lucide-react'
import { fetchTracesPage, extractTraceQuestion } from '../../../shared/api/admin'
import { useAdminContext } from './AdminContext'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Input } from '../ui/input'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'
import { formatDateTime } from '../../../shared/lib/format'
import { MetricsDashboard } from './MetricsDashboard'
import { SemanticSearchUI } from './SemanticSearchUI'
import { buildConversationHref } from '../../../shared/lib/admin-links'

const PAGE_SIZE = 80

export function ChatTracesLegacy() {
  const [searchParams, setSearchParams] = useSearchParams()
  const auth = useAdminContext()
  const hasAdminKey = !!auth.adminKey.trim()

  const initialSearch = searchParams.get('search') || ''
  const [search, setSearch] = useState(initialSearch)
  const deferredSearch = useDeferredValue(search)

  useEffect(() => {
    setSearchParams((prev) => {
      if (search.trim()) prev.set('search', search.trim())
      else prev.delete('search')
      return prev
    })
  }, [search, setSearchParams])

  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    error,
  } = useInfiniteQuery({
    queryKey: ['traces-page', auth.adminKey, deferredSearch],
    queryFn: ({ pageParam }) =>
      fetchTracesPage(auth.adminKey, {
        limit: PAGE_SIZE,
        cursor: (pageParam as string | undefined) ?? undefined,
        search: deferredSearch,
      }),
    enabled: hasAdminKey,
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor || undefined,
  })

  const traces = useMemo(
    () => data?.pages.flatMap((page) => page.items ?? []) ?? [],
    [data],
  )

  const openTrace = (id: string) => {
    setSearchParams((prev) => {
      prev.set('traceId', id)
      return prev
    })
  }

  if (!hasAdminKey) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Admin API key is required to view traces.</AlertDescription>
      </Alert>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{(error as Error).message}</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Evaluation & Traces</h1>
        <div className="relative w-72">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search traces/session/question…"
            className="pl-8 h-9 text-sm bg-white"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <Tabs defaultValue="traces" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="traces">Search Traces</TabsTrigger>
          <TabsTrigger value="metrics">Metrics Summary</TabsTrigger>
          <TabsTrigger value="semantic">Semantic Search</TabsTrigger>
        </TabsList>

        <TabsContent value="traces">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-semibold">Execution Traces ({traces.length})</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {isLoading ? (
                <div className="p-4 space-y-2">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 rounded" />
                  ))}
                </div>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 border-b">
                        <tr>
                          <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase">Status</th>
                          <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase">Trace ID</th>
                          <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase">Input Preview</th>
                          <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase">Model</th>
                          <th className="px-4 py-2.5 text-right text-xs font-semibold text-muted-foreground uppercase">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {traces.map((t) => (
                          <tr key={t.trace_id} className="border-b last:border-0 hover:bg-slate-50/50 transition-colors">
                            <td className="px-4 py-3">
                              {t.error ? <XCircle size={16} className="text-red-500" /> : <CheckCircle2 size={16} className="text-emerald-500" />}
                            </td>
                            <td className="px-4 py-3 font-mono text-xs text-slate-500">{t.trace_id}</td>
                            <td className="px-4 py-3 font-medium text-slate-700 max-w-[320px] truncate">
                              {extractTraceQuestion(t) || t.final_output?.slice(0, 80) || '—'}
                              <div className="text-[10px] text-slate-400 mt-0.5">{formatDateTime(t.started_at)}</div>
                            </td>
                            <td className="px-4 py-3 text-xs text-slate-500">{t.model ?? '—'}</td>
                            <td className="px-4 py-3 text-right">
                              <div className="inline-flex items-center gap-2">
                                {buildConversationHref(t.session_id) ? (
                                  <Link
                                    to={buildConversationHref(t.session_id)!}
                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-cyan-50 hover:bg-cyan-100 text-cyan-700 rounded-md text-xs font-medium transition-colors border border-cyan-200"
                                  >
                                    <MessageSquare size={12} />
                                    View Conversation
                                  </Link>
                                ) : (
                                  <span className="text-[11px] text-slate-400 px-2">No conversation</span>
                                )}
                                <button
                                  onClick={() => openTrace(t.trace_id)}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-indigo-50 text-indigo-600 rounded-md text-xs font-medium transition-colors"
                                >
                                  Inspect <ExternalLink size={12} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                        {!traces.length && (
                          <tr>
                            <td colSpan={5} className="px-4 py-8 text-center text-sm text-muted-foreground">
                              No traces found
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                  <div className="px-4 py-3 border-t bg-white flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                      Loaded {traces.length} traces
                    </span>
                    <button
                      type="button"
                      onClick={() => fetchNextPage()}
                      disabled={!hasNextPage || isFetchingNextPage}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-semibold disabled:opacity-50"
                    >
                      {isFetchingNextPage ? 'Loading…' : hasNextPage ? 'Load more' : 'No more'}
                    </button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="metrics" className="pt-2">
          <MetricsDashboard />
        </TabsContent>

        <TabsContent value="semantic" className="pt-2">
          <SemanticSearchUI />
        </TabsContent>
      </Tabs>
    </div>
  )
}
