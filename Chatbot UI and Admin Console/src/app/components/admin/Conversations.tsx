import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, MessageSquare } from 'lucide-react'
import { fetchConversations, extractTraceQuestion } from '../../../shared/api/admin'
import { useAdminContext } from './AdminContext'
import { Card } from '../ui/card'
import { Input } from '../ui/input'
import { Skeleton } from '../ui/skeleton'
import { Alert, AlertDescription } from '../ui/alert'
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '../ui/resizable'
import { ScrollArea } from '../ui/scroll-area'
import { formatDateTime } from '../../../shared/lib/format'
import { ChatMessage } from '../ChatMessage'
import type { ChatMessage as ChatMessageType } from '../../../shared/types/chat'

export function Conversations() {
  const auth = useAdminContext()
  const [search, setSearch] = useState('')
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)

  const { data = [], isLoading, error } = useQuery({
    queryKey: ['conversations', auth.adminKey],
    queryFn: () => fetchConversations(auth.adminKey),
    enabled: !!auth.adminKey,
  })

  // Filter list based on search query
  const filtered = data.filter((c) =>
    !search ||
    extractTraceQuestion(c).toLowerCase().includes(search.toLowerCase()) ||
    c.session_id.includes(search)
  )

  const selected = selectedIdx !== null ? filtered[selectedIdx] : null

  // 🚀 PRODUCTION-GRADE PATTERN: 
  // Map the raw Evaluation Trace into strict ChatMessage structures.
  // This allows us to feed the exact same component used by the end-user widget.
  const conversationMessages = useMemo<ChatMessageType[]>(() => {
    if (!selected) return []
    const msgs: ChatMessageType[] = []

    const question = extractTraceQuestion(selected)
    if (question) {
      msgs.push({
        id: `user-${selected.trace_id}`,
        role: 'user',
        content: question,
        reasoning: '',
        timestamp: new Date(selected.started_at || Date.now()).getTime(),
        status: 'done',
        toolCalls: [],
        cost: null,
        router: null,
      })
    }

    if (selected.final_output || selected.error) {
      msgs.push({
        id: `assistant-${selected.trace_id}`,
        role: 'assistant',
        content: selected.final_output || selected.error || '',
        reasoning: '', // Reasoning would map here if exposed at the summary level
        timestamp: new Date(selected.started_at || Date.now()).getTime() + 100,
        status: selected.error ? 'error' : 'done',
        toolCalls: [],
        cost: null,
        router: null,
      })
    }

    return msgs
  }, [selected])

  if (!auth.adminKey) {
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
          <h1 className="text-2xl text-gray-900 tracking-tight" style={{ fontWeight: 700 }}>Conversations</h1>
          <p className="text-gray-500 text-sm mt-1">Review live chat transcripts and AI interactions.</p>
        </div>
        <div className="relative w-full sm:w-72">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <Input
            placeholder="Search queries or sessions…"
            className="pl-9 bg-white shadow-sm h-10 border-gray-200 focus:border-cyan-500 focus:ring-cyan-500/20"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <Card className="overflow-hidden border-gray-200 shadow-md" style={{ height: 'calc(100vh - 220px)', minHeight: 500 }}>
        {/* @ts-expect-error - direction prop exists at runtime for react-resizable-panels */}
        <ResizablePanelGroup direction="horizontal" className="h-full bg-white">

          {/* LEFT PANEL: Conversation List */}
          <ResizablePanel defaultSize={35} minSize={25} className="bg-slate-50/50">
            <ScrollArea className="h-full">
              {isLoading ? (
                <div className="p-4 space-y-3">
                  {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}
                </div>
              ) : (
                <div className="p-3 space-y-1.5">
                  {filtered.map((c, i) => (
                    <button
                      key={c.trace_id}
                      onClick={() => setSelectedIdx(i)}
                      className={`w-full text-left p-4 rounded-xl border transition-all duration-200 ${selectedIdx === i
                          ? 'bg-white border-cyan-300 shadow-[0_2px_10px_-3px_rgba(6,182,212,0.15)] ring-1 ring-cyan-500/20'
                          : 'bg-transparent border-transparent hover:bg-white hover:border-gray-200 hover:shadow-sm'
                        }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono text-[11px] font-bold text-cyan-700 bg-cyan-50 px-2 py-0.5 rounded-md truncate max-w-[140px]">
                          {c.session_id}
                        </span>
                        <span className="text-[10px] text-gray-400 font-medium">
                          {formatDateTime(c.started_at)}
                        </span>
                      </div>
                      <p className="text-sm font-semibold text-gray-700 mt-2 line-clamp-2 leading-snug">
                        {extractTraceQuestion(c) || '—'}
                      </p>
                    </button>
                  ))}
                  {!filtered.length && (
                    <div className="p-8 text-center text-sm text-gray-500 flex flex-col items-center">
                      <MessageSquare size={24} className="mb-2 text-gray-300" />
                      No conversations found
                    </div>
                  )}
                </div>
              )}
            </ScrollArea>
          </ResizablePanel>

          <ResizableHandle withHandle className="w-1.5 bg-gray-100 hover:bg-cyan-200 transition-colors" />

          {/* RIGHT PANEL: Chat Transcript */}
          <ResizablePanel defaultSize={65} minSize={40} className="bg-[#f8fafc] relative">
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
                  {/* Sticky Header */}
                  <div className="px-6 py-4 border-b border-gray-200 bg-white/80 backdrop-blur-md sticky top-0 z-20 shadow-sm">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                          Transcript for <span className="font-mono text-cyan-600 font-semibold">{selected.session_id}</span>
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
                  </div>

                  {/* Rendered Messages using the actual ChatWidget components */}
                  <div className="p-6 space-y-6 max-w-3xl">
                    {conversationMessages.map(msg => (
                      <ChatMessage key={msg.id} message={msg} />
                    ))}
                  </div>
                </div>
              )}
            </ScrollArea>
          </ResizablePanel>
        </ResizablePanelGroup>
      </Card>
    </div>
  )
}