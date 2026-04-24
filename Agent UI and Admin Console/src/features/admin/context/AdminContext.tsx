import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'

/**
 * AdminContext — BYOK provider keys only.
 *
 * The legacy `adminKey` field and the `nbfc_admin_key` localStorage entry
 * were retired in Phase 6g of the admin auth plan (2026-04-11). Admin
 * authentication now flows through AdminAuthProvider (JWT session cookie).
 * This context is kept solely for the three BYOK LLM provider keys used by
 * session-scoped model execution in the model-config page.
 *
 * A one-time migration on mount removes the stale `nbfc_admin_key` entry
 * from localStorage if it exists.
 */
interface AdminContextValue {
  openrouterKey: string
  setOpenrouterKey: (v: string) => void
  nvidiaKey: string
  setNvidiaKey: (v: string) => void
  groqKey: string
  setGroqKey: (v: string) => void
}

const STORAGE = {
  openrouterKey: 'nbfc_openrouter_key',
  nvidiaKey: 'nbfc_nvidia_key',
  groqKey: 'nbfc_groq_key',
} as const

/** Legacy localStorage key retired in Phase 6g — removed on provider mount. */
const LEGACY_ADMIN_KEY_STORAGE = 'nbfc_admin_key'

const AdminContext = createContext<AdminContextValue | null>(null)

function safeGetItem(key: string): string {
  try {
    return localStorage.getItem(key) ?? ''
  } catch {
    return ''
  }
}

function safeRemoveItem(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    // Ignore — localStorage may be unavailable in some sandboxed contexts
  }
}

export function AdminProvider({ children }: { children: React.ReactNode }) {
  const [openrouterKey, _setOpenrouterKey] = useState(() =>
    safeGetItem(STORAGE.openrouterKey),
  )
  const [nvidiaKey, _setNvidiaKey] = useState(() => safeGetItem(STORAGE.nvidiaKey))
  const [groqKey, _setGroqKey] = useState(() => safeGetItem(STORAGE.groqKey))

  // One-time migration: drop the legacy adminKey localStorage entry on mount.
  useEffect(() => {
    safeRemoveItem(LEGACY_ADMIN_KEY_STORAGE)
  }, [])

  const setOpenrouterKey = useCallback((v: string) => {
    localStorage.setItem(STORAGE.openrouterKey, v)
    _setOpenrouterKey(v)
  }, [])

  const setNvidiaKey = useCallback((v: string) => {
    localStorage.setItem(STORAGE.nvidiaKey, v)
    _setNvidiaKey(v)
  }, [])

  const setGroqKey = useCallback((v: string) => {
    localStorage.setItem(STORAGE.groqKey, v)
    _setGroqKey(v)
  }, [])

  return (
    <AdminContext.Provider
      value={{
        openrouterKey,
        setOpenrouterKey,
        nvidiaKey,
        setNvidiaKey,
        groqKey,
        setGroqKey,
      }}
    >
      {children}
    </AdminContext.Provider>
  )
}

export function useAdminContext(): AdminContextValue {
  const ctx = useContext(AdminContext)
  if (!ctx) throw new Error('useAdminContext must be used inside <AdminProvider>')
  return ctx
}
