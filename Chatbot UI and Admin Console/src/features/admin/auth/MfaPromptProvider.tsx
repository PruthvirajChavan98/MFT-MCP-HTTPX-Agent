import { createContext, useCallback, useEffect, useRef, useState, type ReactNode } from 'react'

import { AlertDialog, AlertDialogContent } from '@components/ui/alert-dialog'

import { MfaChallenge } from './MfaChallenge'

/**
 * Dispatched by `http.ts` when a request returns 403 with
 * `detail.code === "mfa_required"`. Caught by `MfaPromptProvider` below so the
 * modal auto-opens for ambient requests that aren't wrapped in `withMfa`.
 */
export const ADMIN_MFA_REQUIRED_EVENT = 'admin:mfa-required'

/**
 * Rejection reason when the user dismisses the MFA modal. Caller code
 * (via `withMfa` in `useMfaPrompt`) can distinguish "user cancelled" from
 * "backend returned a different error" and suppress toasts accordingly.
 */
export class MfaCancelled extends Error {
  constructor(message = 'MFA verification cancelled') {
    super(message)
    this.name = 'MfaCancelled'
  }
}

interface MfaPromptContextValue {
  promptMfa: (actionLabel: string) => Promise<void>
}

/** Null default — the hook throws when consumed outside the provider. */
// eslint-disable-next-line react-refresh/only-export-components
export const MfaPromptContext = createContext<MfaPromptContextValue | null>(null)

interface PromptState {
  open: boolean
  actionLabel: string
}

interface Waiter {
  resolve: () => void
  reject: (err: unknown) => void
}

export function MfaPromptProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PromptState>({ open: false, actionLabel: '' })

  // Multiple concurrent `withMfa` callers share one modal. When the modal
  // resolves (user enters a valid code), every waiter resolves — they all
  // benefit from the same MFA-fresh session. On cancel, every waiter rejects
  // with `MfaCancelled`.
  const waitersRef = useRef<Waiter[]>([])

  const promptMfa = useCallback((actionLabel: string): Promise<void> => {
    return new Promise<void>((resolve, reject) => {
      waitersRef.current.push({ resolve, reject })
      setState((prev) => (prev.open ? prev : { open: true, actionLabel }))
    })
  }, [])

  const resolveAll = useCallback(() => {
    const waiters = waitersRef.current
    waitersRef.current = []
    setState({ open: false, actionLabel: '' })
    waiters.forEach((w) => w.resolve())
  }, [])

  const rejectAll = useCallback((err: unknown) => {
    const waiters = waitersRef.current
    waitersRef.current = []
    setState({ open: false, actionLabel: '' })
    waiters.forEach((w) => w.reject(err))
  }, [])

  const handleCancel = useCallback(() => {
    rejectAll(new MfaCancelled())
  }, [rejectAll])

  // Ambient listener — a request wrapped in `withMfa` handles its own modal
  // open through the context, but `http.ts` also fires this event for the
  // "ambient 403 mfa_required" case (e.g. an unwrapped query that drifted
  // past the 5-min freshness window). Only open if no prompt is already up.
  useEffect(() => {
    const handler = () => {
      if (waitersRef.current.length === 0) {
        // Ambient listener — no one is awaiting the promise we'd return, so
        // swallow the rejection on cancel / unmount to prevent an unhandled
        // promise rejection from appearing in the console.
        promptMfa('continue').catch(() => {})
      }
    }
    window.addEventListener(ADMIN_MFA_REQUIRED_EVENT, handler)
    return () => window.removeEventListener(ADMIN_MFA_REQUIRED_EVENT, handler)
  }, [promptMfa])

  // On unmount, reject any pending waiters so Promise holders never strand.
  useEffect(() => {
    return () => {
      if (waitersRef.current.length > 0) {
        const waiters = waitersRef.current
        waitersRef.current = []
        waiters.forEach((w) => w.reject(new MfaCancelled('provider unmounted')))
      }
    }
  }, [])

  return (
    <MfaPromptContext.Provider value={{ promptMfa }}>
      {children}
      <AlertDialog
        open={state.open}
        onOpenChange={(next) => {
          if (!next) handleCancel()
        }}
      >
        <AlertDialogContent className="max-w-sm p-0 border-0 bg-transparent shadow-none">
          <MfaChallenge
            onVerified={resolveAll}
            onCancel={handleCancel}
            actionLabel={state.actionLabel}
          />
        </AlertDialogContent>
      </AlertDialog>
    </MfaPromptContext.Provider>
  )
}
