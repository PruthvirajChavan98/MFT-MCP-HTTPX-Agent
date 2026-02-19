import { useRef, useEffect } from 'react'
import { Send, Square } from 'lucide-react'
import { cn } from './ui/utils'

interface Props {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  onStop: () => void
  isStreaming: boolean
  disabled?: boolean
}

export function ChatInput({ value, onChange, onSend, onStop, isStreaming, disabled }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }, [value])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!isStreaming && value.trim()) onSend()
    }
  }

  return (
    <div className="flex items-end gap-2 p-3 border-t border-gray-100 bg-white">
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask TrustFin anything…"
        rows={1}
        disabled={disabled || isStreaming}
        className={cn(
          'flex-1 resize-none rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 leading-relaxed placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/50 focus:border-cyan-400 transition-all max-h-[120px] overflow-y-auto',
          (disabled || isStreaming) && 'opacity-60 cursor-not-allowed',
        )}
      />
      {isStreaming ? (
        <button
          onClick={onStop}
          className="flex-shrink-0 w-8 h-8 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center transition-colors"
          title="Stop"
        >
          <Square size={14} className="text-white" />
        </button>
      ) : (
        <button
          onClick={onSend}
          disabled={!value.trim() || disabled}
          className="flex-shrink-0 w-8 h-8 rounded-full bg-cyan-500 hover:bg-cyan-600 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
          title="Send"
        >
          <Send size={14} className="text-white" />
        </button>
      )}
    </div>
  )
}
