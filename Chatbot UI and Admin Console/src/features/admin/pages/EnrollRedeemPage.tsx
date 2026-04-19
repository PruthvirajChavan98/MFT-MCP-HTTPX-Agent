import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { AlertTriangle, Copy, Loader2, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'

import {
  fetchEnrollmentTokenMetadata,
  generateTotpSecretBase32,
  redeemEnrollmentToken,
  type EnrollmentTokenMetadata,
} from '@features/admin/api/adminEnrollment'
import { getErrorMessage } from '@shared/lib/errors'

const TOTP_ISSUER = 'mft-agent-admin'
const MIN_PASSWORD_LENGTH = 12

const INPUT_BASE =
  'w-full rounded-md border bg-background px-3 py-2.5 text-sm text-foreground transition-colors placeholder:text-muted-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/30'
const LABEL_BASE =
  'mb-1.5 block text-[11px] font-tabular uppercase tracking-[0.15em] text-muted-foreground'

function buildOtpauthUri(secretBase32: string, accountName: string): string {
  const label = encodeURIComponent(`${TOTP_ISSUER}:${accountName}`)
  const params = new URLSearchParams({
    secret: secretBase32,
    issuer: TOTP_ISSUER,
  })
  return `otpauth://totp/${label}?${params.toString()}`
}

async function copyToClipboard(value: string, label: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(value)
    toast.success(`${label} copied`)
  } catch {
    toast.error('Clipboard write failed — copy manually')
  }
}

type LoadState =
  | { kind: 'no-token' }
  | { kind: 'loading' }
  | { kind: 'error'; status: number | null; code?: string; message: string }
  | { kind: 'ready'; metadata: EnrollmentTokenMetadata }

export function EnrollRedeemPage() {
  const [searchParams] = useSearchParams()
  const tokenFromUrl = searchParams.get('token')?.trim() ?? ''
  const [tokenInput, setTokenInput] = useState(tokenFromUrl)
  const [loadState, setLoadState] = useState<LoadState>({
    kind: tokenFromUrl ? 'loading' : 'no-token',
  })

  // Password + TOTP state
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [totpSecretBase32] = useState(() => generateTotpSecretBase32())
  const [busy, setBusy] = useState(false)

  const navigate = useNavigate()

  const otpauthUri = useMemo(() => {
    if (loadState.kind !== 'ready') return ''
    return buildOtpauthUri(totpSecretBase32, loadState.metadata.email)
  }, [loadState, totpSecretBase32])

  useEffect(() => {
    if (!tokenFromUrl) return
    let cancelled = false
    void (async () => {
      try {
        const metadata = await fetchEnrollmentTokenMetadata(tokenFromUrl)
        if (cancelled) return
        if (metadata.status !== 'pending') {
          setLoadState({
            kind: 'error',
            status: metadata.status === 'expired' ? 410 : 409,
            code: metadata.status,
            message:
              metadata.status === 'expired'
                ? 'This enrollment link has expired. Ask your super-admin for a new one.'
                : 'This enrollment link has already been used.',
          })
          return
        }
        setLoadState({ kind: 'ready', metadata })
      } catch (err: unknown) {
        if (cancelled) return
        const status =
          err && typeof err === 'object' && 'status' in err
            ? (err as { status: number }).status
            : null
        setLoadState({
          kind: 'error',
          status,
          message: getErrorMessage(err),
        })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [tokenFromUrl])

  const handleSubmitTokenInput = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = tokenInput.trim()
    if (!trimmed) return
    navigate(`/admin/enroll?token=${encodeURIComponent(trimmed)}`, { replace: true })
  }

  const handleRedeem = async (e: React.FormEvent) => {
    e.preventDefault()
    if (loadState.kind !== 'ready') return
    if (password.length < MIN_PASSWORD_LENGTH) {
      toast.error(`Password must be at least ${MIN_PASSWORD_LENGTH} characters`)
      return
    }
    if (password !== confirmPassword) {
      toast.error('Passwords do not match')
      return
    }
    if (!/^\d{6,8}$/.test(totpCode)) {
      toast.error('Enter the 6-digit code from your authenticator app')
      return
    }

    setBusy(true)
    try {
      await redeemEnrollmentToken(tokenFromUrl, {
        password,
        totp_secret_base32: totpSecretBase32,
        totp_code: totpCode,
      })
      toast.success('Account created — welcome!')
      navigate('/admin', { replace: true })
    } catch (err: unknown) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-sm">
        <div className="mb-6 flex items-center gap-2">
          <ShieldCheck className="text-primary" size={20} />
          <h1 className="text-lg font-semibold">Admin enrollment</h1>
        </div>

        {loadState.kind === 'no-token' && (
          <form onSubmit={handleSubmitTokenInput} className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Paste the enrollment token your super-admin gave you.
            </p>
            <div>
              <label className={LABEL_BASE}>Enrollment token</label>
              <input
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                className={`${INPUT_BASE} font-tabular`}
                placeholder="paste token here"
                autoFocus
              />
            </div>
            <button
              type="submit"
              className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Continue
            </button>
          </form>
        )}

        {loadState.kind === 'loading' && (
          <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 size={16} className="animate-spin" />
            Validating token…
          </div>
        )}

        {loadState.kind === 'error' && (
          <div className="space-y-4">
            <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-destructive">
              <AlertTriangle className="mt-0.5 shrink-0" size={16} />
              <div className="text-sm">
                <p className="font-medium">Enrollment link unavailable</p>
                <p className="mt-1 opacity-90">{loadState.message}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => navigate('/admin/login', { replace: true })}
              className="w-full rounded-lg border border-border bg-muted px-4 py-2.5 text-sm font-medium text-foreground hover:bg-accent"
            >
              Back to sign in
            </button>
          </div>
        )}

        {loadState.kind === 'ready' && (
          <form onSubmit={handleRedeem} className="space-y-4">
            <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm">
              <div className="text-muted-foreground text-xs uppercase tracking-[0.15em]">
                Setting up account for
              </div>
              <div className="font-tabular text-foreground mt-1">
                {loadState.metadata.email}
              </div>
              <div className="mt-2 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                Role: {loadState.metadata.role.replace('_', ' ')} · Expires{' '}
                {new Date(loadState.metadata.expires_at).toLocaleString()}
              </div>
            </div>

            <div>
              <label className={LABEL_BASE}>New password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`${INPUT_BASE} font-tabular`}
                placeholder={`Minimum ${MIN_PASSWORD_LENGTH} characters`}
                autoComplete="new-password"
              />
            </div>
            <div>
              <label className={LABEL_BASE}>Confirm password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={`${INPUT_BASE} font-tabular`}
                autoComplete="new-password"
              />
            </div>

            <div className="rounded-lg border border-border bg-muted/30 p-3 space-y-2.5">
              <div className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                Step 1 — Add this secret to your authenticator app
              </div>
              <div className="flex gap-2">
                <input
                  readOnly
                  value={totpSecretBase32}
                  className={`${INPUT_BASE} font-tabular text-xs`}
                />
                <button
                  type="button"
                  aria-label="Copy TOTP secret"
                  onClick={() => copyToClipboard(totpSecretBase32, 'TOTP secret')}
                  className="inline-flex items-center gap-1 rounded-md border border-primary/20 bg-primary/10 px-3 text-xs font-medium text-primary hover:bg-primary/20"
                >
                  <Copy size={12} /> Copy
                </button>
              </div>
              <div className="flex gap-2">
                <input
                  readOnly
                  value={otpauthUri}
                  className={`${INPUT_BASE} font-tabular text-[10px]`}
                />
                <button
                  type="button"
                  aria-label="Copy otpauth URI"
                  onClick={() => copyToClipboard(otpauthUri, 'otpauth URI')}
                  className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-3 text-xs font-medium text-foreground hover:bg-accent"
                >
                  <Copy size={12} /> URI
                </button>
              </div>
              <p className="text-[10px] text-muted-foreground">
                Scan the URI via any authenticator that accepts otpauth://, or paste the
                secret manually (Issuer: {TOTP_ISSUER}).
              </p>
            </div>

            <div>
              <label className={LABEL_BASE}>
                Step 2 — Enter the 6-digit code
              </label>
              <input
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ''))}
                className={`${INPUT_BASE} font-tabular tracking-[0.3em]`}
                placeholder="123456"
                inputMode="numeric"
                maxLength={8}
                autoComplete="one-time-code"
              />
            </div>

            <button
              type="submit"
              disabled={busy}
              className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {busy ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
              Complete enrollment
            </button>
            <button
              type="button"
              onClick={() => navigate('/admin/login', { replace: true })}
              className="w-full text-center text-[11px] text-muted-foreground hover:text-foreground"
            >
              Cancel and go to sign in
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

export default EnrollRedeemPage
