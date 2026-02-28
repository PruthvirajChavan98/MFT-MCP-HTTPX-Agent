import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { Search, MessageSquare, Database, Microscope, DollarSign, Hash } from 'lucide-react'
import {
  fetchConversationsPage,
  fetchEvalSessions,
  fetchSessionCost,
  fetchSessionTraces,
} from '../../../shared/api/admin'
import type { SessionListItem } from '../../../shared/api/admin'
import { useAdminContext } from './AdminContext'
import { Card } from '../ui/card'
import { Input } from '../ui/input'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '../ui/resizable'
import { ScrollArea } from '../ui/scroll-area'
import { formatCurrency, formatDateTime } from '../../../shared/lib/format'
import { ChatMessage } from '../ChatMessage'
import type { ChatMessage as ChatMessageType } from '../../../shared/types/chat'

const PAGE_SIZE = 80

export function Conversations() {
  const auth = useAdminContext()
  const hasAdminKey = !!auth.adminKey.trim()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialSessionId = searchParams.get('sessionId')

  const [search, setSearch] = useState(searchParams.get('search') || '')
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(initialSessionId)
  const deferredSearch = useDeferredValue(search)

  useEffect(() => {
    setSearchParams((prev) => {
      if (search.trim()) prev.set('search', search.trim())
      else prev.delete('search')
      return prev
    })
  }, [search, setSearchParams])

  const {
    data: convPages,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    error,
  } = useInfiniteQuery({
    queryKey: ['conversations-page', auth.adminKey, deferredSearch],
    queryFn: ({ pageParam }) =>
      fetchConversationsPage(auth.adminKey, {
        limit: PAGE_SIZE,
        cursor: (pageParam as string | undefined) ?? undefined,
        search: deferredSearch,
      }),
    enabled: hasAdminKey,
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor || undefined,
  })

  const liveSessions = useMemo(
    () => convPages?.pages.flatMap((page) => page.items ?? []) ?? [],
    [convPages],
  )

  const { data: evalSessions = [], isLoading: evalLoading } = useQuery({
    queryKey: ['eval-sessions', auth.adminKey],
    queryFn: () => fetchEvalSessions(auth.adminKey, 100),
    enabled: hasAdminKey,
  })

  const { data: sessionTraces = [], isLoading: sessionLoading } = useQuery({
    queryKey: ['session-traces', auth.adminKey, selectedSessionId],
    queryFn: () => fetchSessionTraces(auth.adminKey, selectedSessionId!),
    enabled: hasAdminKey && !!selectedSessionId,
  })

  const { data: sessionCost } = useQuery({
    queryKey: ['session-cost-detail', selectedSessionId],
    queryFn: () => fetchSessionCost(selectedSessionId!),
    enabled: hasAdminKey && !!selectedSessionId,
    refetchInterval: 30_000,
  })

  useEffect(() => {
    if (!selectedSessionId && liveSessions.length > 0) {
      const next = liveSessions[0]?.session_id
      if (!next) return
      setSelectedSessionId(next)
      setSearchParams((prev) => {
        prev.set('sessionId', next)
        return prev
      })
    }
  }, [liveSessions, selectedSessionId, setSearchParams])

  const selected =
    liveSessions.find((c: SessionListItem) => c.session_id === selectedSessionId) ||
    (selectedSessionId
      ? {
          session_id: selectedSessionId,
          started_at: sessionTraces.length
            ? new Date(sessionTraces[0].timestamp).toISOString()
            : undefined,
          model: sessionTraces.find((item) => item.role === 'assistant')?.model || 'Agent Session',
          provider: sessionTraces.find((item) => item.role === 'assistant')?.provider,
        }
      : null)

  const handleSelectSession = (sessionId: string) => {
    setSelectedSessionId(sessionId)
    setSearchParams((prev) => {
      prev.set('sessionId', sessionId)
      return prev
    })
  }

  const conversationMessages = sessionTraces as ChatMessageType[]

  if (!hasAdminKey) {
    return (
      <Alert className="max-w-2xl border-amber-200 bg-amber-50 text-amber-800">
        <AlertDescription className="font-medium">
          Set X-Admin-Key in the API Keys header to view conversations.
        </AlertDescription>
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
    <div className="space-y-6 max-w-[1600px] mx-auto pb-10">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl text-gray-900 tracking-tight" style={{ fontWeight: 700 }}>
            Conversations
          </h1>
          <p className="text-gray-500 text-sm mt-1">Review live chat transcripts and AI interactions.</p>
        </div>
        <div className="relative w-full sm:w-80">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <Input
            placeholder="Search queries or sessions…"
            className="pl-9 bg-white shadow-sm h-10 border-gray-200 focus:border-cyan-500 focus:ring-cyan-500/20"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <Tabs defaultValue="live" className="w-full">
        <div className="flex justify-between items-center mb-4">
          <TabsList className="bg-slate-100/80">
            <TabsTrigger value="live" className="text-sm font-semibold flex items-center gap-2">
              <MessageSquare className="w-4 h-4" /> Live Traffic
            </TabsTrigger>
            <TabsTrigger value="evals" className="text-sm font-semibold flex items-center gap-2">
              <Microscope className="w-4 h-4" /> Eval & Debug Sessions
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="live" className="m-0 border-none outline-none">
          <Card
            className="overflow-hidden border-gray-200 shadow-md"
            style={{ height: 'calc(100vh - 220px)', minHeight: 500 }}
          >
            {/* @ts-expect-error direction prop exists at runtime */}
            <ResizablePanelGroup direction="horizontal" className="h-full bg-white">
              <ResizablePanel defaultSize={34} minSize={25} className="bg-slate-50/50">
                <ScrollArea className="h-full">
                  {isLoading ? (
                    <div className="p-4 space-y-3">
                      {Array.from({ length: 8 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 w-full rounded-xl" />
                      ))}
                    </div>
                  ) : (
                    <div className="p-3 space-y-1.5">
                      {liveSessions.map((c) => (
                        <button
                          key={c.session_id}
                          onClick={() => handleSelectSession(c.session_id)}
                          className={`w-full text-left p-4 rounded-xl border transition-all duration-200 ${
                            selectedSessionId === c.session_id
                              ? 'bg-white border-cyan-300 shadow-[0_2px_10px_-3px_rgba(6,182,212,0.15)] ring-1 ring-cyan-500/20'
                              : 'bg-transparent border-transparent hover:bg-white hover:border-gray-200 hover:shadow-sm'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono text-[11px] font-bold text-cyan-700 bg-cyan-50 px-2 py-0.5 rounded-md truncate max-w-[150px]">
                              {c.session_id}
                            </span>
                            <span className="text-[10px] text-gray-400 font-medium">
                              {formatDateTime(c.started_at)}
                            </span>
                          </div>
                          <p className="text-sm font-semibold text-gray-700 mt-2 line-clamp-2 leading-snug">
                            {c.first_question || '—'}
                          </p>
                          <div className="mt-2 text-[11px] text-gray-500">
                            {c.provider || 'unknown'} • {c.model?.split('/').pop() || 'unknown'} •{' '}
                            {c.message_count ?? 0} msgs
                          </div>
                        </button>
                      ))}
                      {!liveSessions.length && (
                        <div className="p-8 text-center text-sm text-gray-500 flex flex-col items-center">
                          <MessageSquare size={24} className="mb-2 text-gray-300" />
                          No conversations found
                        </div>
                      )}
                      <div className="pt-2 flex justify-end">
                        <button
                          type="button"
                          onClick={() => fetchNextPage()}
                          disabled={!hasNextPage || isFetchingNextPage}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-semibold disabled:opacity-50"
                        >
                          {isFetchingNextPage ? 'Loading…' : hasNextPage ? 'Load more' : 'No more'}
                        </button>
                      </div>
                    </div>
                  )}
                </ScrollArea>
              </ResizablePanel>

              <ResizableHandle withHandle className="w-1.5 bg-gray-100 hover:bg-cyan-200 transition-colors" />

              <ResizablePanel defaultSize={66} minSize={40} className="bg-[#f8fafc] relative">
                <ScrollArea className="h-full">
                  {!selected ? (
                    <div className="flex flex-col items-center justify-center h-full text-sm text-gray-400 min-h-[400px]">
                      <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                        <MessageSquare size={24} className="text-gray-300" />
                      </div>
                      Select a conversation from the list to view the transcript
                    </div>
                  ) : (
                    <div className="flex flex-col h-full">
                      <div className="px-6 py-4 border-b border-gray-200 bg-white/80 backdrop-blur-md sticky top-0 z-20 shadow-sm space-y-2">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                              Transcript for{' '}
                              <span className="font-mono text-cyan-600 font-semibold">{selected.session_id}</span>
                            </h3>
                            <div className="text-xs font-medium text-gray-500 mt-1 flex items-center gap-2">
                              <span className="bg-gray-100 px-2 py-0.5 rounded text-gray-600 font-mono">
                                {selected.model?.split('/').pop() ?? 'Unknown Model'}
                              </span>
                              <span>•</span>
                              <span>{formatDateTime(selected.started_at)}</span>
                            </div>
                          </div>
                        </div>
                        <div className="grid grid-cols-3 gap-2 max-w-xl">
                          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                            <div className="text-[10px] uppercase tracking-wide text-slate-500">Total Cost</div>
                            <div className="text-sm font-semibold flex items-center gap-1"><DollarSign size={12} />{formatCurrency(sessionCost?.total_cost ?? 0)}</div>
                          </div>
                          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                            <div className="text-[10px] uppercase tracking-wide text-slate-500">Requests</div>
                            <div className="text-sm font-semibold flex items-center gap-1"><Hash size={12} />{sessionCost?.total_requests ?? 0}</div>
                          </div>
                          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                            <div className="text-[10px] uppercase tracking-wide text-slate-500">Tokens</div>
                            <div className="text-sm font-semibold">{sessionCost?.total_tokens ?? 0}</div>
                          </div>
                        </div>
                      </div>

                      <div className="p-6 space-y-6 max-w-3xl">
                        {sessionLoading ? (
                          <div className="space-y-6">
                            <Skeleton className="h-20 w-3/4 rounded-xl ml-auto" />
                            <Skeleton className="h-32 w-5/6 rounded-xl" />
                            <Skeleton className="h-20 w-3/4 rounded-xl ml-auto" />
                          </div>
                        ) : conversationMessages.length === 0 ? (
                          <div className="flex flex-col items-center justify-center text-sm text-gray-400 py-20">
                            No messages found in this session history.
                          </div>
                        ) : (
                          conversationMessages.map((msg) => (
                            <ChatMessage key={msg.id} message={msg} />
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </ScrollArea>
              </ResizablePanel>
            </ResizablePanelGroup>
          </Card>
        </TabsContent>

        <TabsContent value="evals" className="m-0 border-none outline-none">
          <Card
            className="border-gray-200 shadow-md overflow-hidden bg-white"
            style={{ height: 'calc(100vh - 220px)', minHeight: 500 }}
          >
            <div className="px-6 py-4 border-b border-gray-100 bg-slate-50/50 flex items-center gap-2">
              <Database className="w-5 h-5 text-slate-500" />
              <h3 className="text-gray-900 text-base font-bold">Raw Headless Sessions</h3>
            </div>
            <ScrollArea className="h-[calc(100%-60px)]">
              <div className="p-6">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50">
                    <tr className="border-b border-gray-100">
                      <th className="px-6 py-3 text-left text-xs font-bold text-slate-500 uppercase">Session ID</th>
                      <th className="px-6 py-3 text-right text-xs font-bold text-slate-500 uppercase">Requests</th>
                      <th className="px-6 py-3 text-right text-xs font-bold text-slate-500 uppercase">Last Active</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50/50">
                    {evalLoading ? (
                      Array.from({ length: 5 }).map((_, i) => (
                        <tr key={i}>
                          <td colSpan={3} className="px-6 py-4">
                            <Skeleton className="w-full h-8" />
                          </td>
                        </tr>
                      ))
                    ) : (
                      evalSessions.map((s) => (
                        <tr key={s.session_id} className="hover:bg-slate-50/50 transition-colors">
                          <td className="px-6 py-3 font-mono text-cyan-600 font-bold">{s.session_id}</td>
                          <td className="px-6 py-3 text-right font-mono font-bold text-slate-700">{s.trace_count}</td>
                          <td className="px-6 py-3 text-right text-slate-500 text-xs">
                            {s.last_active ? formatDateTime(s.last_active) : '—'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
                {!evalLoading && evalSessions.length === 0 && (
                  <div className="text-center py-12 text-slate-500">
                    <Microscope className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    No ad-hoc evaluation sessions found.
                  </div>
                )}
              </div>
            </ScrollArea>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
