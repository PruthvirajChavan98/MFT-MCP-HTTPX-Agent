import { useEffect, useRef } from 'react'
import type { ManualCopyPayload } from '@shared/lib/clipboard'

interface Props {
  payload: ManualCopyPayload | null
  onClose: () => void
}

export function ClipboardFallbackModal({ payload, onClose }: Props) {
  const textAreaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!payload) return
    textAreaRef.current?.focus()
    textAreaRef.current?.select()
  }, [payload])

  if (!payload) return null

  return (
    <div className="tf-chat-copy-modal fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/65 px-4">
      <div
        aria-modal="true"
        role="dialog"
        className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-4 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Clipboard access blocked</h3>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              Direct clipboard write was blocked. The content below is selected for manual copy.
            </p>
          </div>
          <button
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
            onClick={onClose}
            type="button"
          >
            Close
          </button>
        </div>

        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
            {payload.kind === 'table' ? 'Table markdown' : 'Code block'}
          </div>
          <textarea
            ref={textAreaRef}
            readOnly
            value={payload.content}
            className="h-56 w-full resize-none rounded-lg border border-slate-200 bg-white p-3 font-mono text-xs leading-6 text-slate-700 outline-none"
          />
        </div>

        <p className="mt-3 text-xs leading-5 text-slate-500">Reason: {payload.reason}</p>
      </div>
    </div>
  )
}
