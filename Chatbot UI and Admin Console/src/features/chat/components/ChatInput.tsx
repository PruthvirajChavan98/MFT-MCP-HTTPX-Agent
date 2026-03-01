import { useRef, useEffect } from 'react'
import { Send, Square } from 'lucide-react'
import { cn } from '@components/ui/utils'

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
  const inputDisabled = disabled || isStreaming

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }, [value])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!isStreaming && !disabled && value.trim()) onSend()
    }
  }

  return (
    <div className="shrink-0 border-t border-slate-200 bg-white px-3.5 pb-3 pt-3 sm:px-4">
      <div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-slate-50/70 px-3 py-2 transition-shadow focus-within:border-cyan-300 focus-within:ring-4 focus-within:ring-cyan-100">
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask TrustFin anything..."
          rows={1}
          disabled={inputDisabled}
          className={cn(
            'max-h-[120px] flex-1 resize-none bg-transparent px-0.5 py-1.5 text-sm leading-6 text-slate-900 outline-none placeholder:text-slate-400',
            inputDisabled && 'cursor-not-allowed opacity-60',
          )}
        />

        {isStreaming ? (
          <button
            onClick={onStop}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-red-500 text-white transition-colors hover:bg-red-600"
            title="Stop generation"
            type="button"
          >
            <Square size={14} />
          </button>
        ) : (
          <button
            onClick={onSend}
            disabled={!value.trim() || !!disabled}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-cyan-500 text-white transition-colors hover:bg-cyan-600 disabled:cursor-not-allowed disabled:opacity-40"
            title="Send message"
            type="button"
          >
            <Send size={14} />
          </button>
        )}
      </div>

      <p className="mt-1.5 hidden text-center text-[11px] text-slate-400 sm:block">
        <kbd className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] text-slate-500">Enter</kbd>{' '}
        to send ·{' '}
        <kbd className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] text-slate-500">
          Shift + Enter
        </kbd>{' '}
        for new line
      </p>
    </div>
  )
}
