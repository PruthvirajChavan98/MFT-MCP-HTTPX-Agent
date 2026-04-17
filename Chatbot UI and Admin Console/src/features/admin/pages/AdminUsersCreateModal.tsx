import { useState } from 'react'
import { AlertTriangle, Check, Copy, Dices, Loader2, X } from 'lucide-react'
import { toast } from 'sonner'

import { MfaCancelled } from '@features/admin/auth/MfaPromptProvider'
import { useMfaPrompt } from '@features/admin/auth/useMfaPrompt'
import { createAdmin, type CreateAdminResult } from '@features/admin/api/admins'

const INPUT_BASE =
  'w-full rounded-md border bg-background px-3 py-2.5 text-sm text-foreground transition-colors placeholder:text-muted-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/30'
const LABEL_BASE =
  'mb-1.5 block text-[11px] font-tabular uppercase tracking-[0.15em] text-muted-foreground'

function randomPassword(length = 20): string {
  const charset =
    'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789-_'
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  let out = ''
  for (let i = 0; i < length; i++) out += charset[bytes[i] % charset.length]
  return out
}

function getErrorMessage(err: unknown): string {
  if (err instanceof Error && err.message.trim()) return err.message
  return 'Request failed'
}

interface Props {
  open: boolean
  created: CreateAdminResult | null
  onSuccess: (result: CreateAdminResult) => void
  onClose: () => void
}

export function AdminUsersCreateModal({ open, created, onSuccess, onClose }: Props) {
  const { withMfa } = useMfaPrompt()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [emailError, setEmailError] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmedSecretSeen, setConfirmedSecretSeen] = useState(false)

  if (!open) return null

  const handleSubmit = async () => {
    const trimmedEmail = email.trim().toLowerCase()
    let hasError = false
    if (!trimmedEmail || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(trimmedEmail)) {
      setEmailError('Enter a valid email address')
      hasError = true
    } else {
      setEmailError('')
    }
    if (password.length < 12) {
      setPasswordError('Password must be at least 12 characters')
      hasError = true
    } else {
      setPasswordError('')
    }
    if (hasError) return

    setBusy(true)
    try {
      const result = await withMfa('enroll a new admin', () =>
        createAdmin({ email: trimmedEmail, password }),
      )
      onSuccess(result)
    } catch (err) {
      if (err instanceof MfaCancelled) return
      toast.error(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const handleClose = () => {
    if (created && !confirmedSecretSeen) {
      if (
        !window.confirm(
          'The TOTP secret and password will not be shown again. Close without copying?',
        )
      ) {
        return
      }
    }
    // Reset local state for the next open.
    setEmail('')
    setPassword('')
    setEmailError('')
    setPasswordError('')
    setConfirmedSecretSeen(false)
    onClose()
  }

  const copyToClipboard = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value)
      toast.success(`${label} copied`)
    } catch {
      toast.error('Clipboard write failed — copy manually')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-lg flex-col rounded-2xl border border-border bg-card shadow-2xl">
        <div className="flex shrink-0 items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-base font-semibold text-foreground">
            {created ? 'Admin enrolled — save these credentials' : 'Add admin'}
          </h2>
          <button
            type="button"
            onClick={handleClose}
            className="rounded-lg p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            aria-label="Close dialog"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {created ? (
            <div className="space-y-4">
              <div className="flex items-start gap-3 rounded-lg border border-[var(--warning)]/30 bg-[var(--warning-soft)] px-4 py-3 text-[var(--warning)]">
                <AlertTriangle className="mt-0.5 shrink-0" size={16} />
                <div className="text-sm">
                  <p className="font-medium">One-time credentials.</p>
                  <p className="mt-1 text-[var(--warning)]/90">
                    Copy these values now. The server will never show the TOTP secret
                    or the initial password again.
                  </p>
                </div>
              </div>

              <div>
                <label className={LABEL_BASE}>Email</label>
                <p className="font-tabular text-sm text-foreground">{created.email}</p>
              </div>

              <CopyRow
                label="Initial password"
                value={password}
                onCopy={() => {
                  copyToClipboard(password, 'Password')
                  setConfirmedSecretSeen(true)
                }}
              />

              <CopyRow
                label="TOTP secret (base32)"
                value={created.totp_secret_base32}
                onCopy={() => {
                  copyToClipboard(created.totp_secret_base32, 'TOTP secret')
                  setConfirmedSecretSeen(true)
                }}
              />

              <CopyRow
                label="TOTP otpauth URI"
                value={created.otpauth_uri}
                onCopy={() => {
                  copyToClipboard(created.otpauth_uri, 'otpauth URI')
                  setConfirmedSecretSeen(true)
                }}
                hint="Paste into any authenticator that supports otpauth:// (or render as a QR code)."
              />

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={handleClose}
                  className="rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  Done
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className={LABEL_BASE}>Email</label>
                <input
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="new-admin@example.com"
                  className={`${INPUT_BASE} ${emailError ? 'border-destructive/60' : 'border-border'}`}
                />
                {emailError && (
                  <p className="mt-1 text-xs text-destructive">{emailError}</p>
                )}
              </div>

              <div>
                <label className={LABEL_BASE}>Initial password</label>
                <div className="flex gap-2">
                  <input
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Minimum 12 characters"
                    type="text"
                    className={`${INPUT_BASE} font-tabular ${passwordError ? 'border-destructive/60' : 'border-border'}`}
                  />
                  <button
                    type="button"
                    onClick={() => setPassword(randomPassword())}
                    className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-3 text-xs font-medium text-foreground hover:bg-accent transition-colors"
                    title="Generate a random password"
                  >
                    <Dices size={14} /> Generate
                  </button>
                </div>
                {passwordError && (
                  <p className="mt-1 text-xs text-destructive">{passwordError}</p>
                )}
                <p className="mt-1 text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">
                  Share this with the new admin out of band (Signal, 1Password, etc.).
                </p>
              </div>
            </div>
          )}
        </div>

        {!created && (
          <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border bg-muted/30 px-6 py-4">
            <button
              type="button"
              onClick={handleClose}
              disabled={busy}
              className="rounded-lg px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={busy}
              className="flex items-center gap-1.5 rounded-xl bg-primary px-5 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              {busy ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Check size={14} />
              )}
              Create admin
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function CopyRow({
  label,
  value,
  onCopy,
  hint,
}: {
  label: string
  value: string
  onCopy: () => void
  hint?: string
}) {
  return (
    <div>
      <label className={LABEL_BASE}>{label}</label>
      <div className="flex gap-2">
        <input
          readOnly
          value={value}
          className={`${INPUT_BASE} border-border font-tabular`}
        />
        <button
          type="button"
          onClick={onCopy}
          className="inline-flex items-center gap-1 rounded-md border border-primary/20 bg-primary/10 px-3 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
        >
          <Copy size={14} /> Copy
        </button>
      </div>
      {hint && (
        <p className="mt-1 text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">
          {hint}
        </p>
      )}
    </div>
  )
}
