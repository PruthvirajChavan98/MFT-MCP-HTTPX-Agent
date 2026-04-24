import { type FormEvent, useState } from 'react'

import { useAdminAuth } from './AdminAuthProvider'

export interface MfaChallengeProps {
  /** Called after successful MFA verification. Parent should retry the gated action. */
  onVerified: () => void
  /** Called when the user dismisses the prompt without verifying. */
  onCancel: () => void
  /** Optional label for the originating action (e.g. "Save FAQ"). */
  actionLabel?: string
}

/**
 * MfaChallenge — modal prompt for TOTP code entry.
 *
 * Shown when a mutation endpoint returns 403 with code=`mfa_required` OR when
 * the parent explicitly requests step-up before performing a super-admin action.
 *
 * The parent is responsible for rendering this inside a modal/dialog surface —
 * this component only provides the form content. Wrap it in whatever Dialog /
 * Sheet / AlertDialog primitive matches the host page.
 */
export function MfaChallenge({ onVerified, onCancel, actionLabel }: MfaChallengeProps) {
  const { verifyMfa } = useAdminAuth()
  const [code, setCode] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (submitting) return
    if (!/^[0-9]{6}$/.test(code)) {
      setError('Enter the 6-digit code from your authenticator app.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await verifyMfa(code)
      onVerified()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Invalid code')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="w-full max-w-sm bg-card rounded-lg shadow-lg p-6 border border-border">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-foreground">Verify to continue</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {actionLabel
            ? `Enter your authenticator code to ${actionLabel.toLowerCase()}.`
            : 'Enter the 6-digit code from your authenticator app.'}
        </p>
      </div>

      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div>
          <label
            htmlFor="admin-mfa-code"
            className="block text-sm font-medium text-foreground mb-1"
          >
            Authenticator code
          </label>
          <input
            id="admin-mfa-code"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            autoFocus
            disabled={submitting}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-center text-lg tracking-[0.4em] font-mono focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          />
        </div>

        {error ? (
          <div
            role="alert"
            className="rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive"
          >
            {error}
          </div>
        ) : null}

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="flex-1 rounded-md border border-input bg-background px-4 py-2 text-sm font-medium hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || code.length !== 6}
            className="flex-1 rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Verifying…' : 'Verify'}
          </button>
        </div>
      </form>
    </div>
  )
}
