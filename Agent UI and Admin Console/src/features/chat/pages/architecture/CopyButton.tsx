import { useCallback, useState } from 'react'
import { Check, Copy } from 'lucide-react'

interface CopyButtonProps {
  value: string
  label?: string
}

export function CopyButton({ value, label = 'Copy' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)

  const handleClick = useCallback(() => {
    if (typeof navigator === 'undefined' || !navigator.clipboard) {
      return
    }
    navigator.clipboard
      .writeText(value)
      .then(() => {
        setCopied(true)
        window.setTimeout(() => setCopied(false), 1500)
      })
      .catch(() => {
        // Permission denied or unsupported — silent. Tests stub this.
      })
  }, [value])

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label={copied ? 'Copied' : label}
      className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-700 bg-slate-900/60 text-slate-400 transition-colors hover:border-cyan-500/40 hover:text-cyan-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}
