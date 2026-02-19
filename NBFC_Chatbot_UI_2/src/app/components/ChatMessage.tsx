import { useState } from 'react'
import { Bot, ChevronDown, ChevronUp, Copy, User, Wrench } from 'lucide-react'
import { Streamdown } from 'streamdown'
import { cn } from './ui/utils'
import { formatCurrency } from '../../shared/lib/format'
import type { ChatMessage as ChatMessageType } from '../../shared/types/chat'

interface Props {
  message: ChatMessageType
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user'
  const [reasoningOpen, setReasoningOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
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
      <div className={cn('max-w-[80%] group', isUser ? 'items-end' : 'items-start', 'flex flex-col gap-1')}>
        <div
          className={cn(
            'px-4 py-3 rounded-2xl text-sm leading-relaxed',
            isUser
              ? 'bg-cyan-500 text-white rounded-tr-sm'
              : 'bg-white border border-gray-100 text-gray-800 rounded-tl-sm shadow-sm',
          )}
        >
          {isUser ? (
            <p>{message.content}</p>
          ) : (
            <div className="prose prose-sm max-w-none [&>*]:my-1">
              {message.status === 'streaming' || message.content ? (
                <Streamdown>{message.content || ' '}</Streamdown>
              ) : null}
            </div>
          )}
        </div>

        {/* Reasoning */}
        {!isUser && message.reasoning && (
          <div className="w-full">
            <button
              onClick={() => setReasoningOpen((p) => !p)}
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors"
            >
              {reasoningOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              Reasoning
            </button>
            {reasoningOpen && (
              <div className="mt-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600 italic">
                {message.reasoning}
              </div>
            )}
          </div>
        )}

        {/* Tool calls */}
        {!isUser && message.toolCalls.length > 0 && (
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

        {/* Footer row: cost + copy */}
        <div className="flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
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
          <span className="text-[10px] text-slate-300">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>
    </div>
  )
}
