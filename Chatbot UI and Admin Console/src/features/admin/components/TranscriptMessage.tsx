import { useState } from 'react'
import { Bot, User } from 'lucide-react'
import { cn } from '@components/ui/utils'
import { AssistantMessageCard } from '@features/chat/components/AssistantMessageCard'
import { copyToClipboard } from '@shared/lib/clipboard'
import type { ChatMessage as ChatMessageType } from '@shared/types/chat'
import { toast } from 'sonner'

interface TranscriptMessageProps {
  message: ChatMessageType
}

export function TranscriptMessage({ message }: TranscriptMessageProps) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)

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

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-xs text-white',
          isUser ? 'bg-cyan-500' : 'bg-slate-700',
        )}
      >
        {isUser ? <User size={14} /> : <Bot size={14} />}
      </div>

      <div className={cn('group flex flex-col gap-1', isUser ? 'max-w-[80%] items-end' : 'w-full items-start')}>
        {isUser ? (
          <div className="rounded-2xl rounded-tr-sm bg-cyan-500 px-4 py-3 text-sm leading-relaxed text-white">
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          </div>
        ) : (
          <AssistantMessageCard
            copied={copied}
            evalStatus={message.evalStatus ?? null}
            followUpsInteractive={false}
            message={message}
            onCopy={handleCopy}
          />
        )}
      </div>
    </div>
  )
}
