import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import {
  CheckCircle2,
  ExternalLink,
  MessageSquare,
  Search,
  XCircle,
  Activity,
} from 'lucide-react'
import { Alert, AlertDescription } from '../../ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card'
import { Input } from '../../ui/input'
import { Skeleton } from '../../ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../ui/tabs'
import { useAdminContext } from '../AdminContext'
import { MetricsDashboard } from '../MetricsDashboard'
import { SemanticSearchUI } from '../SemanticSearchUI'
import { formatDateTime } from '../../../../shared/lib/format'
import { parseToLangsmithTree } from '../trace/parse'
import { TraceInspector } from '../trace/TraceInspector'
import { TraceTree } from '../trace/TraceTree'
import {
  adminTraceQueryOptions,
  tracesPageInfiniteQueryOptions,
} from '../viewmodels/queryOptions'
import {
  mapTraceDetailToViewer,
  mapTraceListRows,
} from '../viewmodels/traces'

const PAGE_SIZE = 80

export function ChatTracesEnterprise() {
  const [searchParams, setSearchParams] = useSearchParams()
  const auth = useAdminContext()
  const hasAdminKey = Boolean(auth.adminKey.trim())

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

  const tracesQuery = useInfiniteQuery(
    tracesPageInfiniteQueryOptions({
      adminKey: auth.adminKey,
      search: deferredSearch,
      limit: PAGE_SIZE,
    }),
  )

  const traces = useMemo(
    () => tracesQuery.data?.pages.flatMap((page) => page.items ?? []) ?? [],
    [tracesQuery.data],
  )

  const rows = useMemo(() => mapTraceListRows(traces), [traces])
  const selectedTraceId = searchParams.get('traceId') || rows[0]?.traceId || null

  useEffect(() => {
    if (!rows.length || searchParams.get('traceId')) return

    setSearchParams((prev) => {
      prev.set('traceId', rows[0].traceId)
      return prev
    })
  }, [rows, searchParams, setSearchParams])

  const [selectedNodeId, setSelectedNodeId] = useState('root')
  useEffect(() => {
    setSelectedNodeId('root')
  }, [selectedTraceId])

  const traceDetailQuery = useQuery(adminTraceQueryOptions(auth.adminKey, selectedTraceId))
  const traceDetail = mapTraceDetailToViewer(traceDetailQuery.data)
  const traceNodes = useMemo(
    () => (traceDetail ? parseToLangsmithTree(traceDetail) : []),
    [traceDetail],
  )
  const selectedNode = traceNodes.find((node) => node.id === selectedNodeId) || traceNodes[0] || null

  const openTrace = (traceId: string) => {
    setSearchParams((prev) => {
      prev.set('traceId', traceId)
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

  if (tracesQuery.error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{(tracesQuery.error as Error).message}</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-sky-50 p-2 dark:bg-sky-500/10">
            <Activity className="size-5 text-sky-500" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-foreground">Evaluation & Traces</h1>
            <p className="text-xs text-muted-foreground">Inspect trace execution waterfall and node-level IO.</p>
          </div>
        </div>

        <div className="relative w-full max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search traces/session/question…"
            className="h-9 bg-card pl-8 text-sm"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </div>

      <Tabs defaultValue="traces" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="traces">Search Traces</TabsTrigger>
          <TabsTrigger value="metrics">Metrics Summary</TabsTrigger>
          <TabsTrigger value="semantic">Semantic Search</TabsTrigger>
        </TabsList>

        <TabsContent value="traces" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-semibold">Trace Catalog ({rows.length})</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {tracesQuery.isLoading ? (
                <div className="space-y-2 p-4">
                  {Array.from({ length: 8 }).map((_, index) => (
                    <Skeleton key={index} className="h-12 rounded" />
                  ))}
                </div>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="border-b bg-muted/40">
                        <tr>
                          <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-muted-foreground">Status</th>
                          <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-muted-foreground">Trace ID</th>
                          <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-muted-foreground">Input Preview</th>
                          <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-muted-foreground">Model</th>
                          <th className="px-4 py-2.5 text-right text-xs font-semibold uppercase text-muted-foreground">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((row) => {
                          const isSelected = row.traceId === selectedTraceId
                          return (
                            <tr
                              key={row.traceId}
                              className={`border-b transition-colors last:border-0 ${
                                isSelected ? 'bg-sky-50/50 dark:bg-sky-500/10' : 'hover:bg-muted/40'
                              }`}
                            >
                              <td className="px-4 py-3">
                                {row.status === 'error' ? (
                                  <XCircle size={16} className="text-rose-500" />
                                ) : (
                                  <CheckCircle2 size={16} className="text-emerald-500" />
                                )}
                              </td>
                              <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{row.traceId}</td>
                              <td className="max-w-[340px] truncate px-4 py-3 text-xs font-medium text-foreground">
                                {row.inputPreview}
                                <div className="mt-0.5 text-[10px] text-muted-foreground">{formatDateTime(row.startedAt)}</div>
                              </td>
                              <td className="px-4 py-3 text-xs text-muted-foreground">{row.model}</td>
                              <td className="px-4 py-3 text-right">
                                <div className="inline-flex items-center gap-2">
                                  {row.conversationHref ? (
                                    <Link
                                      to={row.conversationHref}
                                      className="inline-flex items-center gap-1.5 rounded-md border border-cyan-200 bg-cyan-50 px-3 py-1.5 text-xs font-medium text-cyan-700 transition-colors hover:bg-cyan-100 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-300 dark:hover:bg-cyan-500/20"
                                    >
                                      <MessageSquare size={12} />
                                      Conversation
                                    </Link>
                                  ) : (
                                    <span className="px-2 text-[11px] text-muted-foreground">No conversation</span>
                                  )}
                                  <button
                                    type="button"
                                    onClick={() => openTrace(row.traceId)}
                                    className="inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-3 py-1.5 text-xs font-medium text-indigo-600 transition-colors hover:bg-indigo-50 dark:bg-slate-800 dark:text-indigo-300 dark:hover:bg-indigo-500/20"
                                  >
                                    Inspect <ExternalLink size={12} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          )
                        })}
                        {!rows.length && (
                          <tr>
                            <td colSpan={5} className="px-4 py-10 text-center text-sm text-muted-foreground">
                              No traces found.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>

                  <div className="flex items-center justify-between border-t bg-card px-4 py-3">
                    <span className="text-xs text-muted-foreground">Loaded {rows.length} traces</span>
                    <button
                      type="button"
                      onClick={() => tracesQuery.fetchNextPage()}
                      disabled={!tracesQuery.hasNextPage || tracesQuery.isFetchingNextPage}
                      className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
                    >
                      {tracesQuery.isFetchingNextPage
                        ? 'Loading…'
                        : tracesQuery.hasNextPage
                          ? 'Load more'
                          : 'No more'}
                    </button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
            {traceDetailQuery.isLoading ? (
              <div className="space-y-3 p-6">
                <Skeleton className="h-10 w-64 rounded" />
                <Skeleton className="h-[420px] rounded" />
              </div>
            ) : traceDetailQuery.error ? (
              <div className="p-6">
                <Alert variant="destructive">
                  <AlertDescription>{(traceDetailQuery.error as Error).message}</AlertDescription>
                </Alert>
              </div>
            ) : traceNodes.length ? (
              <div className="overflow-x-auto">
                <div className="flex h-[calc(100vh-290px)] min-h-[520px] min-w-[900px]">
                  <TraceTree
                    nodes={traceNodes}
                    selectedNodeId={selectedNodeId}
                    onSelect={setSelectedNodeId}
                    onClose={() => setSearchParams((prev) => {
                      prev.delete('traceId')
                      return prev
                    })}
                    isLoading={false}
                  />
                  <TraceInspector node={selectedNode} />
                </div>
              </div>
            ) : (
              <div className="flex min-h-[220px] items-center justify-center text-sm text-muted-foreground">
                Select a trace to inspect.
              </div>
            )}
          </div>
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
