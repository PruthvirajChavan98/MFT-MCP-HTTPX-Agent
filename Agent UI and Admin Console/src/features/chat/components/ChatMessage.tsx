import { useState } from 'react'
import { Bot, User } from 'lucide-react'
import { cn } from '@components/ui/utils'
import type { ChatMessage as ChatMessageType } from '@shared/types/chat'
import { submitFeedback } from '@features/chat/api/chat'
import { toast } from 'sonner'
import { copyToClipboard } from '@shared/lib/clipboard'
import { useEvalStatus } from '@features/chat/hooks/useEvalStatus'
import { AssistantMessageCard } from './AssistantMessageCard'

interface Props {
  message: ChatMessageType
  sessionId?: string
  onFollowUpClick?: (text: string) => void
}

export function ChatMessage({ message, sessionId, onFollowUpClick }: Props) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)
  const [feedbackState, setFeedbackState] = useState<'idle' | 'thumbs_up' | 'thumbs_down'>('idle')
  const evalStatus = useEvalStatus(isUser ? undefined : message.traceId)

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
        {isUser ? (
          <div className="rounded-2xl rounded-tr-sm bg-cyan-500 px-4 py-3 text-sm leading-relaxed text-white">
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          </div>
        ) : (
          <AssistantMessageCard
            copied={copied}
            evalStatus={evalStatus}
            feedbackState={feedbackState}
            message={message}
            onCopy={handleCopy}
            onFeedback={sessionId ? handleFeedback : undefined}
            onFollowUpClick={onFollowUpClick}
          />
        )}
      </div>
    </div>
  )
}
