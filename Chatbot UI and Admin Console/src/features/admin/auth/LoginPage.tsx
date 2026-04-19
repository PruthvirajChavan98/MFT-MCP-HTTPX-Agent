import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router'

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
    <div className="relative min-h-screen flex items-center justify-center bg-background p-4 overflow-hidden">
      {/* Atmosphere — restrained cyan radial wash anchoring the form */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{ backgroundImage: 'var(--atmosphere-radial-1)' }}
      />
      {/* Grid hairline — optical anchor, almost imperceptible */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            'linear-gradient(var(--foreground) 1px, transparent 1px), linear-gradient(90deg, var(--foreground) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />

      <div className="relative w-full max-w-sm">
        {/* Product mark above the card — terminal-style identity line */}
        <div className="flex items-center justify-center gap-2.5 mb-6">
          <span
            className="size-8 rounded-md flex items-center justify-center bg-primary/10 text-primary ring-1 ring-primary/20"
            aria-hidden
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="size-4">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </span>
          <div className="flex flex-col leading-tight">
            <span className="text-[13px] font-semibold tracking-tight">MFT Admin</span>
            <span className="text-[10px] font-tabular uppercase tracking-[0.2em] text-muted-foreground">
              production console
            </span>
          </div>
        </div>

        <div className="bg-card/80 backdrop-blur-xl rounded-lg border border-border p-7 shadow-[0_20px_60px_-20px_rgba(0,0,0,0.35)]">
          <div className="mb-6">
            <h1 className="text-xl font-semibold tracking-tight text-foreground">Sign in</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Enter your admin credentials to continue.
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <div>
              <label
                htmlFor="admin-login-email"
                className="block text-[11px] font-tabular uppercase tracking-[0.15em] text-muted-foreground mb-1.5"
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
                className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm transition-colors placeholder:text-muted-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/30 disabled:opacity-50"
              />
            </div>

            <div>
              <label
                htmlFor="admin-login-password"
                className="block text-[11px] font-tabular uppercase tracking-[0.15em] text-muted-foreground mb-1.5"
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
                className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm transition-colors placeholder:text-muted-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/30 disabled:opacity-50"
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
              className="w-full h-10 rounded-md bg-primary text-primary-foreground text-sm font-medium transition-[background-color,transform] duration-150 hover:bg-primary/90 active:translate-y-px focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card disabled:opacity-50 disabled:cursor-not-allowed disabled:active:translate-y-0"
            >
              {submitting ? 'Signing in…' : 'Sign in'}
            </button>

            <div className="flex items-center justify-center pt-1">
              <kbd className="text-[10px] font-tabular text-muted-foreground">
                press <span className="border border-border rounded px-1 mx-0.5">enter</span> to submit
              </kbd>
            </div>

            <div className="pt-3 text-center text-xs text-muted-foreground">
              Have an enrollment token?{' '}
              <Link
                to="/admin/enroll"
                className="font-medium text-primary hover:underline"
              >
                Enroll →
              </Link>
            </div>
          </form>
        </div>

        <p className="mt-5 text-xs text-muted-foreground text-center max-w-sm">
          After signing in, you will be prompted for your authenticator code before
          performing knowledge-base changes.
        </p>
      </div>
    </div>
  )
}
