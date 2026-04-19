import { useState } from 'react'
import { Copy, Loader2, ShieldCheck, X } from 'lucide-react'
import { toast } from 'sonner'

import { MfaCancelled } from '@features/admin/auth/MfaPromptProvider'
import { useMfaPrompt } from '@features/admin/auth/useMfaPrompt'
import {
  issueEnrollmentToken,
  type IssueEnrollmentTokenResponse,
} from '@features/admin/api/adminEnrollment'
import { getErrorMessage } from '@shared/lib/errors'

const INPUT_BASE =
  'w-full rounded-md border bg-background px-3 py-2.5 text-sm text-foreground transition-colors placeholder:text-muted-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/30'
const LABEL_BASE =
  'mb-1.5 block text-[11px] font-tabular uppercase tracking-[0.15em] text-muted-foreground'

interface Props {
  open: boolean
  onClose: () => void
}

async function copyToClipboard(value: string, label: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(value)
    toast.success(`${label} copied`)
  } catch {
    toast.error('Clipboard write failed — copy manually')
  }
}

export function AdminEnrollTokenModal({ open, onClose }: Props) {
  const { withMfa } = useMfaPrompt()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'admin' | 'super_admin'>('admin')
  const [ttlHours, setTtlHours] = useState(24)
  const [busy, setBusy] = useState(false)
  const [issued, setIssued] = useState<IssueEnrollmentTokenResponse | null>(null)
  const [emailError, setEmailError] = useState('')

  if (!open) return null

  const handleIssue = async () => {
    const normalized = email.trim().toLowerCase()
    if (!normalized || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(normalized)) {
      setEmailError('Enter a valid email address')
      return
    }
    setEmailError('')

    setBusy(true)
    try {
      const result = await withMfa('issue an enrollment token', () =>
        issueEnrollmentToken({ email: normalized, role, ttl_hours: ttlHours }),
      )
      setIssued(result)
    } catch (err) {
      if (err instanceof MfaCancelled) return
      toast.error(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const handleClose = () => {
    setEmail('')
    setRole('admin')
    setTtlHours(24)
    setEmailError('')
    setIssued(null)
    onClose()
  }

  const redeemUrlFull = (() => {
    if (!issued) return ''
    if (issued.redeem_url.startsWith('http')) return issued.redeem_url
    return `${window.location.origin}${issued.redeem_url}`
  })()

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-lg flex-col rounded-2xl border border-border bg-card shadow-2xl">
        <div className="flex shrink-0 items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-base font-semibold text-foreground">
            {issued ? 'Enrollment link — share this with the new admin' : 'Generate enrollment link'}
          </h2>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close dialog"
            className="rounded-lg p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {issued ? (
            <div className="space-y-4">
              <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm">
                <div className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                  For
                </div>
                <div className="font-tabular mt-1">{issued.email}</div>
                <div className="mt-1 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                  Role: {issued.role.replace('_', ' ')} · Expires{' '}
                  {new Date(issued.expires_at).toLocaleString()}
                </div>
              </div>

              <div>
                <label className={LABEL_BASE}>Redeem URL</label>
                <div className="flex gap-2">
                  <input readOnly value={redeemUrlFull} className={`${INPUT_BASE} font-tabular text-xs`} />
                  <button
                    type="button"
                    aria-label="Copy redeem URL"
                    onClick={() => copyToClipboard(redeemUrlFull, 'Redeem URL')}
                    className="inline-flex items-center gap-1 rounded-md border border-primary/20 bg-primary/10 px-3 text-xs font-medium text-primary hover:bg-primary/20"
                  >
                    <Copy size={12} /> URL
                  </button>
                </div>
                <p className="mt-1 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                  Send via a secure channel (Signal, 1Password). Single-use, expires as shown.
                </p>
              </div>

              <div>
                <label className={LABEL_BASE}>Raw token</label>
                <div className="flex gap-2">
                  <input readOnly value={issued.token} className={`${INPUT_BASE} font-tabular text-xs`} />
                  <button
                    type="button"
                    aria-label="Copy raw token"
                    onClick={() => copyToClipboard(issued.token, 'Token')}
                    className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-3 text-xs font-medium text-foreground hover:bg-accent"
                  >
                    <Copy size={12} /> Token
                  </button>
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={handleClose}
                  className="rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
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
                {emailError && <p className="mt-1 text-xs text-destructive">{emailError}</p>}
              </div>

              <div>
                <label className={LABEL_BASE}>Role</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value as 'admin' | 'super_admin')}
                  className={INPUT_BASE}
                >
                  <option value="admin">admin</option>
                  <option value="super_admin">super_admin</option>
                </select>
              </div>

              <div>
                <label className={LABEL_BASE}>TTL (hours, max 168)</label>
                <input
                  type="number"
                  min={1}
                  max={168}
                  value={ttlHours}
                  onChange={(e) => setTtlHours(Number(e.target.value) || 24)}
                  className={`${INPUT_BASE} font-tabular`}
                />
              </div>

              <p className="text-xs text-muted-foreground">
                The new admin opens the redeem URL, sets their own password + TOTP, and is
                logged in automatically. The server never sees their password in plaintext.
              </p>
            </div>
          )}
        </div>

        {!issued && (
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
              onClick={handleIssue}
              disabled={busy}
              className="flex items-center gap-1.5 rounded-xl bg-primary px-5 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90 disabled:opacity-50"
            >
              {busy ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
              Generate link
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
