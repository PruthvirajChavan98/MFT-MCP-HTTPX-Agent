import { useState } from 'react'
import {
  ArrowUpRight,
  ChevronDown,
  ChevronUp,
  Copy,
  ThumbsDown,
  ThumbsUp,
  Wrench,
} from 'lucide-react'
import { cn } from '@components/ui/utils'
import { buildTraceHref } from '@shared/lib/navigation'
import { ChatAssistantMarkdown } from './ChatAssistantMarkdown'
import { formatCurrency } from '@shared/lib/format'
import type { ChatMessage as ChatMessageType, EvalStatus } from '@shared/types/chat'

type FeedbackState = 'idle' | 'thumbs_up' | 'thumbs_down'

interface AssistantMessageCardProps {
  message: ChatMessageType
  copied?: boolean
  evalStatus?: EvalStatus | null
  feedbackState?: FeedbackState
  followUpsInteractive?: boolean
  onCopy?: () => void
  onFeedback?: (rating: 'thumbs_up' | 'thumbs_down') => void
  onFollowUpClick?: (text: string) => void
}

function formatToolOutput(output: string) {
  if (!output.trim()) return output
  try {
    return JSON.stringify(JSON.parse(output), null, 2)
  } catch {
    return output
  }
}

function renderEvalBadge(evalStatus: EvalStatus | null | undefined) {
  if (!evalStatus || evalStatus.status === 'not_found') return null

  if (evalStatus.status === 'pending') {
    return (
      <>
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-slate-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-slate-400" />
        </span>
        Evaluating...
      </>
    )
  }

  if (evalStatus.status === 'complete' && (evalStatus.failed ?? 0) === 0) {
    return (
      <>
        <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
        <span className="text-emerald-600">Eval passed</span>
      </>
    )
  }

  if (evalStatus.status === 'complete') {
    return (
      <>
        <span className="inline-flex h-2 w-2 rounded-full bg-amber-500" />
        <span className="text-amber-600">
          Eval: {evalStatus.passed ?? 0}/{(evalStatus.passed ?? 0) + (evalStatus.failed ?? 0)} passed
        </span>
      </>
    )
  }

  const label = evalStatus.reason === 'sampled_out'
    ? 'Eval skipped'
    : evalStatus.reason === 'timed_out'
      ? 'Eval timed out'
      : 'Eval unavailable'

  return (
    <>
      <span className="inline-flex h-2 w-2 rounded-full bg-slate-400" />
      <span className="text-slate-500">{label}</span>
    </>
  )
}

export function AssistantMessageCard({
  message,
  copied = false,
  evalStatus = null,
  feedbackState = 'idle',
  followUpsInteractive = true,
  onCopy,
  onFeedback,
  onFollowUpClick,
}: AssistantMessageCardProps) {
  const [reasoningOpen, setReasoningOpen] = useState(false)
  const [toolCallsOpen, setToolCallsOpen] = useState(false)
  const cleanContent = message.content.replace(/\n?FOLLOW_UPS:[\s\S]*$/s, '').trimEnd()
  const hasReasoning = !!message.reasoning
  const hasToolCalls = (message.toolCalls?.length ?? 0) > 0
  const traceHref = buildTraceHref(message.traceId)
  const evalBadge = renderEvalBadge(evalStatus)
  const feedbackEnabled = Boolean(onFeedback)

  return (
    <div className="group flex w-full flex-col gap-1 items-start">
      <div
        data-testid="assistant-bubble"
        className="overflow-hidden rounded-2xl rounded-tl-sm border border-gray-100 bg-white text-sm leading-relaxed text-gray-800 shadow-sm"
      >
        {(hasReasoning || hasToolCalls) && (
          <div className="border-b border-slate-100 px-4 py-3">
            <div className="flex flex-wrap items-center gap-3">
              {hasReasoning && (
                <button
                  aria-expanded={reasoningOpen}
                  className="flex items-center gap-1 text-xs text-slate-400 transition-colors hover:text-slate-600"
                  onClick={() => setReasoningOpen((open) => !open)}
                  type="button"
                >
                  {reasoningOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  Reasoning
                </button>
              )}
              {hasToolCalls && (
                <button
                  aria-expanded={toolCallsOpen}
                  className="flex items-center gap-1 text-xs text-slate-400 transition-colors hover:text-slate-600"
                  onClick={() => setToolCallsOpen((open) => !open)}
                  type="button"
                >
                  {toolCallsOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  Raw tool calls
                </button>
              )}
            </div>
            {hasReasoning && reasoningOpen && (
              <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs italic text-slate-600">
                {message.reasoning}
              </div>
            )}
            {hasToolCalls && toolCallsOpen && (
              <div className="mt-2 space-y-2 rounded-lg border border-slate-200 bg-slate-950 px-3 py-2 text-xs text-slate-100">
                {message.toolCalls?.map((toolCall, index) => (
                  <div key={`${toolCall.tool_call_id}-${index}`} className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
                      <span className="font-semibold text-slate-100">{toolCall.name}</span>
                      <span className="font-mono text-slate-400">{toolCall.tool_call_id}</span>
                    </div>
                    <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded border border-slate-800 bg-slate-900 px-2 py-1.5 font-mono text-[11px] text-slate-100">
                      {formatToolOutput(toolCall.output)}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div
          className={cn('px-4 pb-3', hasReasoning || hasToolCalls ? 'pt-3' : 'py-3')}
          data-testid="assistant-bubble-content"
        >
          <ChatAssistantMarkdown content={cleanContent} status={message.status} />
        </div>
      </div>

      {hasToolCalls && (
        <div className="flex flex-wrap gap-1">
          {message.toolCalls?.map((toolCall, index) => (
            <span
              key={`${toolCall.tool_call_id}-${index}`}
              className="inline-flex items-center gap-1 rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-700"
            >
              <Wrench size={10} />
              {toolCall.name}
            </span>
          ))}
        </div>
      )}

      {(message.followUps?.length ?? 0) > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {message.followUps?.map((item, index) => (
            followUpsInteractive && onFollowUpClick ? (
              <button
                key={`${item}-${index}`}
                className="inline-flex cursor-pointer items-center rounded-full border border-cyan-200 bg-cyan-50 px-2 py-0.5 text-[10px] font-medium text-cyan-700 transition-colors hover:bg-cyan-100"
                onClick={() => onFollowUpClick(item)}
                type="button"
              >
                {item}
              </button>
            ) : (
              <span
                key={`${item}-${index}`}
                className="inline-flex items-center rounded-full border border-cyan-200 bg-cyan-50 px-2 py-0.5 text-[10px] font-medium text-cyan-700"
              >
                {item}
              </span>
            )
          ))}
        </div>
      )}

      {traceHref && (
        <a
          className="group/trace mt-1.5 flex w-max items-center gap-1 rounded-md border border-transparent px-2 py-1 text-[11px] font-medium text-slate-400 transition-colors hover:border-cyan-100 hover:text-cyan-600"
          href={traceHref}
          rel="noopener noreferrer"
          target="_blank"
        >
          <div className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-slate-100 group-hover/trace:bg-cyan-50">
            <span className="mb-[1px] text-[8px] font-bold leading-none text-slate-500 group-hover/trace:text-cyan-600">❖</span>
          </div>
          View trace
          <ArrowUpRight size={10} className="-ml-0.5 opacity-0 transition-opacity group-hover/trace:opacity-100" />
        </a>
      )}

      {evalBadge && (
        <span className="inline-flex w-max items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-slate-400">
          {evalBadge}
        </span>
      )}

      {message.status === 'error' && !message.traceId && (
        <span className="mt-1.5 inline-flex w-max items-center rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-medium text-slate-500">
          Trace unavailable for this failed stream
        </span>
      )}

      <div className="mt-1 flex items-center gap-3 opacity-0 transition-opacity group-hover:opacity-100">
        {message.cost && (
          <span className="text-[10px] text-slate-400">{formatCurrency(message.cost.total_cost)}</span>
        )}
        {message.content && onCopy && (
          <button
            className="flex items-center gap-1 text-[10px] text-slate-400 transition-colors hover:text-slate-600"
            onClick={onCopy}
            type="button"
          >
            <Copy size={10} />
            {copied ? 'Copied!' : 'Copy'}
          </button>
        )}

        {feedbackEnabled && message.status === 'done' && (
          <div className="ml-1 flex items-center gap-0.5">
            <button
              className={cn(
                'flex h-5 w-5 items-center justify-center rounded transition-colors hover:bg-slate-100',
                feedbackState === 'thumbs_up'
                  ? 'bg-green-50 text-green-600'
                  : 'text-slate-400 hover:text-green-600',
              )}
              disabled={feedbackState !== 'idle'}
              onClick={() => onFeedback?.('thumbs_up')}
              title="Good response"
              type="button"
            >
              <ThumbsUp size={11} className={feedbackState === 'thumbs_up' ? 'fill-current' : ''} />
            </button>
            <button
              className={cn(
                'flex h-5 w-5 items-center justify-center rounded transition-colors hover:bg-slate-100',
                feedbackState === 'thumbs_down'
                  ? 'bg-red-50 text-red-600'
                  : 'text-slate-400 hover:text-red-600',
              )}
              disabled={feedbackState !== 'idle'}
              onClick={() => onFeedback?.('thumbs_down')}
              title="Bad response"
              type="button"
            >
              <ThumbsDown size={11} className={feedbackState === 'thumbs_down' ? 'fill-current' : ''} />
            </button>
          </div>
        )}

        <span className="ml-auto text-[10px] text-slate-300">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  )
}
