import { useEffect, useMemo } from 'react'
import { Search, MessageSquare, Database, Microscope, DollarSign, Hash, Bot } from 'lucide-react'
import { Card } from '@components/ui/card'
import { Input } from '@components/ui/input'
import { Skeleton } from '@components/ui/skeleton'
import { Alert, AlertDescription } from '@components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@components/ui/tabs'
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@components/ui/resizable'
import { ScrollArea } from '@components/ui/scroll-area'
import { formatCurrency, formatDateTime } from '@shared/lib/format'
import { TranscriptMessage } from '@features/admin/components/TranscriptMessage'
import { useAdminContext } from '@features/admin/context/AdminContext'
import { useConversationSelection } from '@features/admin/hooks/useConversationSelection'
import {
  useConversationQueries,
  resolveSelectedSession,
  type ResolvedSession,
} from '@features/admin/hooks/useConversationQueries'
import type { SessionListItem } from '@features/admin/api/admin'

// ── Sub-components (extracted for clarity) ──────────────────────────────────

function SessionCard({
  session,
  isSelected,
  onSelect,
}: {
  session: SessionListItem
  isSelected: boolean
  onSelect: (id: string) => void
}) {
  return (
    <button
      key={session.session_id}
      onClick={() => onSelect(session.session_id)}
      className={`w-full text-left p-4 rounded-xl border transition-all duration-200 ${
        isSelected
          ? 'bg-white border-cyan-300 shadow-[0_2px_10px_-3px_rgba(6,182,212,0.15)] ring-1 ring-cyan-500/20'
          : 'bg-transparent border-transparent hover:bg-white hover:border-gray-200 hover:shadow-sm'
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-[11px] font-bold text-cyan-700 bg-cyan-50 px-2 py-0.5 rounded-md truncate max-w-[150px]">
          {session.session_id}
        </span>
        <span className="text-[10px] text-gray-400 font-medium">
          {formatDateTime(session.started_at)}
        </span>
      </div>
      <p className="text-sm font-semibold text-gray-700 mt-2 line-clamp-2 leading-snug">
        {session.first_question || '\u2014'}
      </p>
      <div className="mt-2 text-[11px] text-gray-500">
        {session.provider || 'unknown'} \u2022 {session.model?.split('/').pop() || 'unknown'} \u2022{' '}
        {session.message_count ?? 0} msgs
      </div>
    </button>
  )
}

function TranscriptHeader({
  resolved,
  sessionCost,
}: {
  resolved: ResolvedSession
  sessionCost: {
    total_cost?: number
    total_requests?: number
    total_tokens?: number
  } | null
}) {
  if (!resolved) return null

  const session = resolved.data

  return (
    <div className="px-6 py-4 border-b border-gray-200 bg-white/80 backdrop-blur-md sticky top-0 z-20 shadow-sm space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
            Transcript for{' '}
            <span className="font-mono text-cyan-600 font-semibold">{session.session_id}</span>
          </h3>
          <div className="text-xs font-medium text-gray-500 mt-1 flex items-center gap-2">
            <span className="bg-gray-100 px-2 py-0.5 rounded text-gray-600 font-mono">
              {session.model?.split('/').pop() ?? 'Unknown Model'}
            </span>
            <span>\u2022</span>
            <span>{formatDateTime(session.started_at)}</span>
            {resolved.kind === 'partial' && (
              <>
                <span>\u2022</span>
                <span className="text-amber-600 text-[10px] font-semibold uppercase">
                  Not in current search
                </span>
              </>
            )}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 max-w-xl">
        <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
          <div className="text-[10px] uppercase tracking-wide text-slate-500">Total Cost</div>
          <div className="text-sm font-semibold flex items-center gap-1">
            <DollarSign size={12} />
            {formatCurrency(sessionCost?.total_cost ?? 0)}
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
          <div className="text-[10px] uppercase tracking-wide text-slate-500">Requests</div>
          <div className="text-sm font-semibold flex items-center gap-1">
            <Hash size={12} />
            {sessionCost?.total_requests ?? 0}
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
          <div className="text-[10px] uppercase tracking-wide text-slate-500">Tokens</div>
          <div className="text-sm font-semibold">{sessionCost?.total_tokens ?? 0}</div>
        </div>
      </div>
    </div>
  )
}

function EmptyTranscriptState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-sm text-gray-400 min-h-[400px]">
      <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
        <MessageSquare size={24} className="text-gray-300" />
      </div>
      Select a conversation from the list to view the transcript
    </div>
  )
}

function EmptyListState() {
  return (
    <div className="p-8 text-center text-sm text-gray-500 flex flex-col items-center">
      <MessageSquare size={24} className="mb-2 text-gray-300" />
      No conversations found
    </div>
  )
}

// ── Main component ──────────────────────────────────────────────────────────

export function Conversations() {
  const auth = useAdminContext()

  // URL-driven state — no useState for sessionId or search
  const selection = useConversationSelection()

  // All queries centralized — proper staleTime, placeholderData
  const queries = useConversationQueries({
    adminKey: auth.adminKey,
    deferredSearch: selection.deferredSearch,
    sessionId: selection.sessionId,
  })

  // Type-safe session resolution — no synthetic objects with missing fields
  const resolved = useMemo(
    () =>
      resolveSelectedSession(
        selection.sessionId,
        queries.conversations,
        queries.sessionTraces,
      ),
    [selection.sessionId, queries.conversations, queries.sessionTraces],
  )

  /**
   * Auto-select: only fires ONCE when:
   * 1. No sessionId in URL
   * 2. Conversation list has loaded with results
   *
   * Does NOT re-fire on search changes — the existing selection
   * persists in the URL independently of list contents.
   */
  useEffect(() => {
    if (selection.sessionId) return
    if (queries.conversationsQuery.isLoading) return
    if (!queries.conversations.length) return

    const first = queries.conversations[0]
    if (first?.session_id) {
      selection.selectSession(first.session_id)
    }
  }, [
    selection.sessionId,
    queries.conversationsQuery.isLoading,
    queries.conversations,
    selection.selectSession,
  ])

  // ── Guards ──────────────────────────────────────────────────────────────

  if (queries.conversationsQuery.error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {(queries.conversationsQuery.error as Error).message}
        </AlertDescription>
      </Alert>
    )
  }

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 max-w-[1600px] mx-auto pb-10">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl text-gray-900 tracking-tight" style={{ fontWeight: 700 }}>
            Conversations
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            Review live chat transcripts and AI interactions.
          </p>
        </div>
        <div className="relative w-full sm:w-80">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <Input
            placeholder="Search queries or sessions\u2026"
            className="pl-9 bg-white shadow-sm h-10 border-gray-200 focus:border-cyan-500 focus:ring-cyan-500/20"
            value={selection.search}
            onChange={(e) => selection.setSearch(e.target.value)}
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
            {/* @ts-expect-error react-resizable-panels direction prop exists at runtime but missing from type defs */}
            <ResizablePanelGroup direction="horizontal" className="h-full bg-white">
              <ResizablePanel defaultSize={34} minSize={25} className="bg-slate-50/50">
                <ScrollArea className="h-full">
                  {queries.conversationsQuery.isLoading ? (
                    <div className="p-4 space-y-3">
                      {Array.from({ length: 8 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 w-full rounded-xl" />
                      ))}
                    </div>
                  ) : (
                    <div className="p-3 space-y-1.5">
                      {queries.conversations.map((c) => (
                        <SessionCard
                          key={c.session_id}
                          session={c}
                          isSelected={selection.sessionId === c.session_id}
                          onSelect={selection.selectSession}
                        />
                      ))}

                      {!queries.conversations.length && <EmptyListState />}

                      <div className="pt-2 flex justify-end">
                        <button
                          type="button"
                          onClick={() => queries.conversationsQuery.fetchNextPage()}
                          disabled={
                            !queries.conversationsQuery.hasNextPage ||
                            queries.conversationsQuery.isFetchingNextPage
                          }
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-semibold disabled:opacity-50"
                        >
                          {queries.conversationsQuery.isFetchingNextPage
                            ? 'Loading\u2026'
                            : queries.conversationsQuery.hasNextPage
                              ? 'Load more'
                              : 'No more'}
                        </button>
                      </div>
                    </div>
                  )}
                </ScrollArea>
              </ResizablePanel>

              <ResizableHandle
                withHandle
                className="w-1.5 bg-gray-100 hover:bg-cyan-200 transition-colors"
              />

              <ResizablePanel defaultSize={66} minSize={40} className="bg-[#f8fafc] relative">
                <ScrollArea className="h-full">
                  {!resolved ? (
                    <EmptyTranscriptState />
                  ) : (
                    <div className="flex flex-col h-full">
                      <TranscriptHeader resolved={resolved} sessionCost={queries.sessionCost} />

                      <div className="flex-1 min-h-0 p-6 max-w-3xl">
                        <div className="flex flex-col rounded-2xl border border-border overflow-hidden h-full">
                          <header className="flex shrink-0 items-center gap-3 border-b border-cyan-400/20 bg-gradient-to-r from-cyan-500 to-teal-500 p-4 text-white">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/20">
                              <Bot size={18} />
                            </div>
                            <div className="min-w-0">
                              <h3 className="truncate text-sm font-bold tracking-tight">
                                Mock FinTech Assistant
                              </h3>
                              <p className="text-xs text-white/80">Session replay</p>
                            </div>
                          </header>
                          <div className="flex-1 overflow-y-auto bg-slate-50/80 px-4 py-4 space-y-4">
                            {queries.sessionTracesLoading ? (
                              <div className="space-y-6">
                                <Skeleton className="h-20 w-3/4 rounded-xl ml-auto" />
                                <Skeleton className="h-32 w-5/6 rounded-xl" />
                                <Skeleton className="h-20 w-3/4 rounded-xl ml-auto" />
                              </div>
                            ) : queries.sessionTraces.length === 0 ? (
                              <div className="flex flex-col items-center justify-center text-sm text-gray-400 py-20">
                                No messages found in this session history.
                              </div>
                            ) : (
                              queries.sessionTraces.map((msg) => (
                                <TranscriptMessage key={msg.id} message={msg} />
                              ))
                            )}
                          </div>
                        </div>
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
                      <th className="px-6 py-3 text-left text-xs font-bold text-slate-500 uppercase">
                        Session ID
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-bold text-slate-500 uppercase">
                        Requests
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-bold text-slate-500 uppercase">
                        Last Active
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50/50">
                    {queries.evalLoading ? (
                      Array.from({ length: 5 }).map((_, i) => (
                        <tr key={i}>
                          <td colSpan={3} className="px-6 py-4">
                            <Skeleton className="w-full h-8" />
                          </td>
                        </tr>
                      ))
                    ) : (
                      queries.evalSessions.map((s) => (
                        <tr
                          key={s.session_id}
                          className="hover:bg-slate-50/50 transition-colors"
                        >
                          <td className="px-6 py-3 font-mono text-cyan-600 font-bold">
                            {s.session_id}
                          </td>
                          <td className="px-6 py-3 text-right font-mono font-bold text-slate-700">
                            {s.trace_count}
                          </td>
                          <td className="px-6 py-3 text-right text-slate-500 text-xs">
                            {s.last_active ? formatDateTime(s.last_active) : '\u2014'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
                {!queries.evalLoading && queries.evalSessions.length === 0 && (
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
