import { useCallback, useContext } from 'react'

import { ApiError } from '@/shared/api/http'

import { MfaPromptContext } from './MfaPromptProvider'

export interface UseMfaPromptValue {
  /** Open the MFA modal manually and await the verification outcome. */
  promptMfa: (actionLabel: string) => Promise<void>
  /**
   * Run an async operation, catching 403 `mfa_required`, prompting for TOTP,
   * and retrying once. All other errors propagate untouched. Cancel rejects
   * with `MfaCancelled` (export from `MfaPromptProvider`).
   */
  withMfa: <T>(actionLabel: string, fn: () => Promise<T>) => Promise<T>
}

function isMfaRequired(err: unknown): err is ApiError {
  if (!(err instanceof ApiError)) return false
  if (err.status !== 403) return false
  const detail = err.detail
  if (typeof detail !== 'object' || detail === null) return false
  const code = (detail as { code?: unknown }).code
  return code === 'mfa_required'
}

/**
 * Hook into the MFA prompt surface mounted by `MfaPromptProvider`.
 *
 * Typical usage inside a mutation:
 *
 * ```ts
 * const { withMfa } = useMfaPrompt()
 * const deleteMut = useMutation({
 *   mutationFn: (row) => withMfa('delete this FAQ', () => api.deleteFaq(row.id))
 * })
 * ```
 *
 * On a cancelled modal the returned Promise rejects with `MfaCancelled`; the
 * mutation's `onError` can branch on `err instanceof MfaCancelled` to
 * suppress a user-facing toast for that specific case.
 */
export function useMfaPrompt(): UseMfaPromptValue {
  const ctx = useContext(MfaPromptContext)
  if (ctx === null) {
    throw new Error('useMfaPrompt must be used inside a <MfaPromptProvider>')
  }
  const { promptMfa } = ctx

  const withMfa = useCallback(
    async <T>(actionLabel: string, fn: () => Promise<T>): Promise<T> => {
      try {
        return await fn()
      } catch (err) {
        if (!isMfaRequired(err)) throw err
        // Prompt; throws MfaCancelled on cancel (propagated to caller).
        await promptMfa(actionLabel)
        // Retry once — any further failure (including another 403 mfa_required,
        // which would be unusual immediately post-verify) propagates.
        return await fn()
      }
    },
    [promptMfa],
  )

  return { promptMfa, withMfa }
}
