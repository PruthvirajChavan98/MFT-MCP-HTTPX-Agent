import { useState } from 'react'
import { Bot, ChevronDown, ChevronUp, Copy, User, Wrench, ThumbsUp, ThumbsDown, ArrowUpRight } from 'lucide-react'
import { cn } from '@components/ui/utils'
import { formatCurrency } from '@shared/lib/format'
import type { ChatMessage as ChatMessageType } from '@shared/types/chat'
import { submitFeedback } from '@features/chat/api/chat'
import { toast } from 'sonner'
import { copyToClipboard } from '@shared/lib/clipboard'
import { ChatAssistantMarkdown } from './ChatAssistantMarkdown'

interface Props {
  message: ChatMessageType
  sessionId?: string
  onFollowUpClick?: (text: string) => void
}

export function ChatMessage({ message, sessionId, onFollowUpClick }: Props) {
  const isUser = message.role === 'user'
  const [reasoningOpen, setReasoningOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [feedbackState, setFeedbackState] = useState<'idle' | 'thumbs_up' | 'thumbs_down'>('idle')

  const handleCopy = async () => {
    const result = await copyToClipboard(message.content)
    if (result.status === 'success') {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
      return
    }

    if (result.status === 'manual') {
      toast.error('Clipboard access is blocked in this environment.')
      return
    }

    toast.error(result.message)
  }

  const handleFeedback = async (rating: 'thumbs_up' | 'thumbs_down') => {
    if (feedbackState !== 'idle') return
    setFeedbackState(rating)
    try {
      await submitFeedback({
        session_id: sessionId,
        trace_id: message.traceId,
        rating
      })
      toast.success('Feedback submitted')
    } catch (err) {
      toast.error('Failed to submit feedback')
      setFeedbackState('idle')
    }
  }

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      {/* Avatar */}
      <div
        className={cn(
          'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white text-xs',
          isUser ? 'bg-cyan-500' : 'bg-slate-700',
        )}
      >
        {isUser ? <User size={14} /> : <Bot size={14} />}
      </div>

      {/* Bubble */}
      <div className={cn('group flex flex-col gap-1', isUser ? 'max-w-[80%] items-end' : 'w-full items-start')}>
        <div
          data-testid={isUser ? undefined : 'assistant-bubble'}
          className={cn(
            'rounded-2xl text-sm leading-relaxed',
            isUser
              ? 'bg-cyan-500 px-4 py-3 text-white rounded-tr-sm'
              : 'overflow-hidden border border-gray-100 bg-white text-gray-800 rounded-tl-sm shadow-sm',
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          ) : (
            <>
              {message.reasoning && (
                <div className="border-b border-slate-100 px-4 py-3">
                  <button
                    aria-expanded={reasoningOpen}
                    onClick={() => setReasoningOpen((p) => !p)}
                    className="flex items-center gap-1 text-xs text-slate-400 transition-colors hover:text-slate-600"
                    type="button"
                  >
                    {reasoningOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    Reasoning
                  </button>
                  {reasoningOpen && (
                    <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs italic text-slate-600">
                      {message.reasoning}
                    </div>
                  )}
                </div>
              )}

              <div
                className={cn('px-4 pb-3', message.reasoning ? 'pt-3' : 'py-3')}
                data-testid="assistant-bubble-content"
              >
                <ChatAssistantMarkdown content={message.content} status={message.status} />
              </div>
            </>
          )}
        </div>

        {/* Tool calls */}
        {!isUser && (message.toolCalls?.length ?? 0) > 0 && (
          <div className="flex flex-wrap gap-1">
            {message.toolCalls.map((tc, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700"
              >
                <Wrench size={10} />
                {tc.name}
              </span>
            ))}
          </div>
        )}

        {!isUser && (message.followUps?.length ?? 0) > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {message.followUps?.map((item, index) => (
              <button
                key={`${item}-${index}`}
                type="button"
                className="inline-flex items-center rounded-full border border-cyan-200 bg-cyan-50 px-2 py-0.5 text-[10px] font-medium text-cyan-700 hover:bg-cyan-100 transition-colors cursor-pointer"
                onClick={() => onFollowUpClick?.(item)}
              >
                {item}
              </button>
            ))}
          </div>
        )}

        {/* Trace Link */}
        {!isUser && message.traceId && (
          <a
            href={`/admin/traces?traceId=${message.traceId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 mt-1.5 text-[11px] text-slate-400 hover:text-cyan-600 transition-colors w-max font-medium group/trace border border-transparent hover:border-cyan-100 px-2 py-1 -ml-2 rounded-md"
          >
            <div className="w-3.5 h-3.5 rounded-full bg-slate-100 group-hover/trace:bg-cyan-50 flex items-center justify-center">
              <span className="text-slate-500 group-hover/trace:text-cyan-600 font-bold leading-none text-[8px] mb-[1px]">❖</span>
            </div>
            View trace
            <ArrowUpRight size={10} className="opacity-0 group-hover/trace:opacity-100 transition-opacity -ml-0.5" />
          </a>
        )}
        {!isUser && message.status === 'error' && !message.traceId && (
          <span className="mt-1.5 inline-flex w-max items-center rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-medium text-slate-500">
            Trace unavailable for this failed stream
          </span>
        )}

        {/* Footer row: cost + copy + time + feedback */}
        <div className="flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity mt-1">
          {!isUser && message.cost && (
            <span className="text-[10px] text-slate-400">
              {formatCurrency(message.cost.total_cost)}
            </span>
          )}
          {!isUser && message.content && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-600 transition-colors"
            >
              <Copy size={10} />
              {copied ? 'Copied!' : 'Copy'}
            </button>
          )}

          {!isUser && message.status === 'done' && sessionId && (
            <div className="flex items-center gap-0.5 ml-1">
              <button
                onClick={() => handleFeedback('thumbs_up')}
                disabled={feedbackState !== 'idle'}
                className={cn("flex items-center justify-center w-5 h-5 transition-colors rounded hover:bg-slate-100", feedbackState === 'thumbs_up' ? "text-green-600 bg-green-50" : "text-slate-400 hover:text-green-600")}
                title="Good response"
              >
                <ThumbsUp size={11} className={feedbackState === 'thumbs_up' ? "fill-current" : ""} />
              </button>
              <button
                onClick={() => handleFeedback('thumbs_down')}
                disabled={feedbackState !== 'idle'}
                className={cn("flex items-center justify-center w-5 h-5 transition-colors rounded hover:bg-slate-100", feedbackState === 'thumbs_down' ? "text-red-600 bg-red-50" : "text-slate-400 hover:text-red-600")}
                title="Bad response"
              >
                <ThumbsDown size={11} className={feedbackState === 'thumbs_down' ? "fill-current" : ""} />
              </button>
            </div>
          )}

          <span className="text-[10px] text-slate-300 ml-auto">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>
    </div>
  )
}
