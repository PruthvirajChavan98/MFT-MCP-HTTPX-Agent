import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import {
  CheckCircle2,
  ExternalLink,
  MessageSquare,
  Search,
  XCircle,
  Activity,
} from 'lucide-react'
import { Alert, AlertDescription } from '@components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Input } from '@components/ui/input'
import { ResponsiveTable, type Column } from '@components/ui/responsive-table'
import { Skeleton } from '@components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@components/ui/tabs'
import { MetricsDashboard } from './MetricsDashboard'
import { SemanticSearchUI } from './SemanticSearchUI'
import { formatDateTime } from '@shared/lib/format'
import { setTraceIdSearchParams } from '@features/admin/lib/admin-links'
import { tracesPageInfiniteQueryOptions } from '@features/admin/query/queryOptions'
import { mapTraceListRows, type TraceListRow } from './viewmodel'

const PAGE_SIZE = 80

const traceColumns: Column<TraceListRow>[] = [
  { key: 'status', label: 'Status' },
  { key: 'traceId', label: 'Trace ID' },
  { key: 'inputPreview', label: 'Input Preview' },
  { key: 'model', label: 'Model', visibleFrom: 'md' },
  { key: 'action', label: 'Action', headerClassName: 'text-right' },
]

export function ChatTracesPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const initialSearch = searchParams.get('search') || ''
  const [search, setSearch] = useState(initialSearch)
  const deferredSearch = useDeferredValue(search)
  const normalizedSearch = search.trim()
  const currentSearchParam = searchParams.get('search') || ''

  // Canonical category slug — deep-link from /admin/categories. Read-only;
  // the active category is surfaced as a pill that can be cleared by the
  // user. Not tied to any input box.
  const categoryFilter = searchParams.get('category') || ''

  useEffect(() => {
    if (currentSearchParam === normalizedSearch) return

    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (normalizedSearch) next.set('search', normalizedSearch)
        else next.delete('search')
        return next
      },
      { replace: true },
    )
  }, [currentSearchParam, normalizedSearch, setSearchParams])

  const tracesQuery = useInfiniteQuery(
    tracesPageInfiniteQueryOptions({
      search: deferredSearch,
      category: categoryFilter || undefined,
      limit: PAGE_SIZE,
    }),
  )

  const clearCategoryFilter = () => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('category')
        return next
      },
      { replace: true },
    )
  }

  const traces = useMemo(
    () => tracesQuery.data?.pages.flatMap((page) => page.items ?? []) ?? [],
    [tracesQuery.data],
  )

  const rows = useMemo(() => mapTraceListRows(traces), [traces])
  const selectedTraceId = searchParams.get('traceId')

  const openTrace = (traceId: string) => {
    setSearchParams((prev) => setTraceIdSearchParams(prev, traceId), { replace: false })
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
          <div className="rounded-md bg-primary/10 p-2 ring-1 ring-primary/20">
            <Activity className="size-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-foreground">Evaluation & Traces</h1>
            <p className="text-xs text-muted-foreground">Inspect trace execution waterfall and node-level IO.</p>
          </div>
        </div>

        <div className="relative w-full sm:max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search traces/session/question…"
            className="h-9 bg-card pl-8 text-sm"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </div>

      {categoryFilter ? (
        <div className="flex items-center gap-2 text-xs">
          <span className="font-tabular uppercase tracking-[0.18em] text-muted-foreground">
            category
          </span>
          <span className="inline-flex items-center gap-2 rounded-md border border-primary/20 bg-primary/10 px-2 py-1 font-tabular text-primary">
            {categoryFilter}
            <button
              type="button"
              onClick={clearCategoryFilter}
              aria-label="Clear category filter"
              className="text-primary/70 hover:text-primary"
            >
              <XCircle className="size-3.5" />
            </button>
          </span>
        </div>
      ) : null}

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
                  <ResponsiveTable<TraceListRow>
                    columns={traceColumns}
                    data={rows}
                    renderCell={(row, column) => {
                      switch (column.key) {
                        case 'status':
                          return row.status === 'error'
                            ? <XCircle size={16} className="text-destructive" />
                            : <CheckCircle2 size={16} className="text-[var(--success)]" />
                        case 'traceId':
                          return <span className="font-tabular text-xs text-primary">{row.traceId}</span>
                        case 'inputPreview':
                          return (
                            <div className="max-w-25 md:max-w-50 lg:max-w-85 truncate">
                              <span className="text-xs font-medium text-foreground">{row.inputPreview}</span>
                              <div className="mt-0.5 text-[10px] text-muted-foreground">{formatDateTime(row.startedAt)}</div>
                            </div>
                          )
                        case 'model':
                          return <span className="text-xs text-muted-foreground">{row.model}</span>
                        case 'action':
                          return (
                            <div className="inline-flex flex-col sm:flex-row items-end sm:items-center gap-1 sm:gap-2">
                              {row.conversationHref ? (
                                <Link
                                  to={row.conversationHref}
                                  className="inline-flex items-center gap-1.5 rounded-md border border-primary/20 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
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
                                className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/40 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent"
                              >
                                Inspect <ExternalLink size={12} />
                              </button>
                            </div>
                          )
                        default:
                          return null
                      }
                    }}
                    emptyMessage="No traces found."
                  />

                  <div className="flex items-center justify-between border-t bg-card px-4 py-3">
                    <span className="text-xs text-muted-foreground">Loaded {rows.length} traces</span>
                    <button
                      type="button"
                      onClick={() => tracesQuery.fetchNextPage()}
                      disabled={!tracesQuery.hasNextPage || tracesQuery.isFetchingNextPage}
                      className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
                    >
                      {tracesQuery.isFetchingNextPage
                        ? 'Loading...'
                        : tracesQuery.hasNextPage
                          ? 'Load more'
                          : 'No more'}
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
