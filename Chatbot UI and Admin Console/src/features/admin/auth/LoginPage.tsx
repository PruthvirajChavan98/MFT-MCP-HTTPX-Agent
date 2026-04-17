import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router'

import { ADMIN_MFA_REQUIRED_EVENT } from '@/shared/api/http'

import { useAdminAuth } from './AdminAuthProvider'

/**
 * LoginPage — email/password form that POSTs to /admin/auth/login.
 *
 * On success, navigates to /admin. If the backend response includes
 * `mfa_required: true`, fires `ADMIN_MFA_REQUIRED_EVENT` after navigate so
 * that `MfaPromptProvider` (mounted inside `AdminLayout`'s AuthGuard) opens
 * the TOTP modal immediately. This avoids a separate /admin/mfa-required
 * route and reuses the same modal surface used by mutation-level MFA prompts.
 *
 * This page is NOT gated by the admin route guard — it's the entry point.
 * The guard in AdminLayout (Phase 5b) redirects to this page when the session
 * is missing.
 */
export function LoginPage() {
  const { login, isLoading, error } = useAdminAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    setLocalError(null)
    try {
      const { mfa_required } = await login(email, password)
      navigate('/admin', { replace: true })
      if (mfa_required) {
        // Fire after navigate so MfaPromptProvider (inside the AdminLayout
        // subtree) is mounted and can receive the event on the next tick.
        window.dispatchEvent(new CustomEvent(ADMIN_MFA_REQUIRED_EVENT))
      }
    } catch (err: unknown) {
      setLocalError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  const displayError = localError ?? error

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md bg-card rounded-lg shadow-lg p-8 border border-border">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-foreground">Admin Sign In</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Enter your admin credentials to continue.
          </p>
        </div>

        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div>
            <label
              htmlFor="admin-login-email"
              className="block text-sm font-medium text-foreground mb-1"
            >
              Email
            </label>
            <input
              id="admin-login-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={submitting || isLoading}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
            />
          </div>

          <div>
            <label
              htmlFor="admin-login-password"
              className="block text-sm font-medium text-foreground mb-1"
            >
              Password
            </label>
            <input
              id="admin-login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={submitting || isLoading}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
            />
          </div>

          {displayError ? (
            <div
              role="alert"
              className="rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive"
            >
              {displayError}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={submitting || isLoading || !email || !password}
            className="w-full rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mt-6 text-xs text-muted-foreground text-center">
          After signing in, you will be prompted for your authenticator code before
          performing knowledge-base changes.
        </p>
      </div>
    </div>
  )
}
