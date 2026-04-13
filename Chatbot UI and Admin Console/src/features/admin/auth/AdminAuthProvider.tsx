import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'

import { ApiError, requestJson } from '@/shared/api/http'

export interface AdminSession {
  sub: string
  roles: readonly string[]
  mfa_fresh: boolean
  exp: number
}

export interface AdminAuthValue {
  session: AdminSession | null
  isLoading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<{ mfa_required: boolean }>
  logout: () => Promise<void>
  verifyMfa: (code: string) => Promise<void>
  refreshSession: () => Promise<void>
}

const AdminAuthContext = createContext<AdminAuthValue | null>(null)

interface LoginResponse {
  ok: boolean
  mfa_required: boolean
}

/**
 * AdminAuthProvider — React context for JWT-cookie-backed admin sessions.
 *
 * On mount, calls GET /admin/auth/me to hydrate session state from the httpOnly
 * cookie. Components use `useAdminAuth()` to access login/logout/verifyMfa/refresh.
 *
 * Replaces the legacy AdminContext X-Admin-Key state. The legacy provider stays
 * around during dual-run (Phases 4-5) for the 3 BYOK LLM provider keys, but the
 * `nbfc_admin_key` localStorage entry is retired.
 */
export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AdminSession | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refreshSession = useCallback(async () => {
    setIsLoading(true)
    try {
      const me = await requestJson<AdminSession>({
        method: 'GET',
        path: '/admin/auth/me',
      })
      setSession(me)
      setError(null)
    } catch (err: unknown) {
      setSession(null)
      // 401 is expected when no session cookie — silent, not an error
      if (err instanceof ApiError && err.status !== 401) {
        setError(err.message)
      } else {
        setError(null)
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshSession()
  }, [refreshSession])

  const login = useCallback(
    async (email: string, password: string): Promise<{ mfa_required: boolean }> => {
      setError(null)
      try {
        const response = await requestJson<LoginResponse>({
          method: 'POST',
          path: '/admin/auth/login',
          body: { email, password },
        })
        await refreshSession()
        return { mfa_required: response.mfa_required }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'login failed'
        setError(message)
        throw err
      }
    },
    [refreshSession],
  )

  const logout = useCallback(async (): Promise<void> => {
    try {
      await requestJson({ method: 'POST', path: '/admin/auth/logout' })
    } catch {
      // Logout is best-effort: even if the server call fails, clear local state
    } finally {
      setSession(null)
      setError(null)
    }
  }, [])

  const verifyMfa = useCallback(
    async (code: string): Promise<void> => {
      setError(null)
      try {
        await requestJson({
          method: 'POST',
          path: '/admin/auth/mfa/verify',
          body: { code },
        })
        await refreshSession()
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'MFA verification failed'
        setError(message)
        throw err
      }
    },
    [refreshSession],
  )

  return (
    <AdminAuthContext.Provider
      value={{
        session,
        isLoading,
        error,
        login,
        logout,
        verifyMfa,
        refreshSession,
      }}
    >
      {children}
    </AdminAuthContext.Provider>
  )
}

export function useAdminAuth(): AdminAuthValue {
  const ctx = useContext(AdminAuthContext)
  if (!ctx) {
    throw new Error('useAdminAuth must be used inside <AdminAuthProvider>')
  }
  return ctx
}
