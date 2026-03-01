import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'

interface AdminContextValue {
  adminKey: string
  setAdminKey: (v: string) => void
  openrouterKey: string
  setOpenrouterKey: (v: string) => void
  groqKey: string
  setGroqKey: (v: string) => void
}

const STORAGE = {
  adminKey: 'nbfc_admin_key',
  openrouterKey: 'nbfc_openrouter_key',
  groqKey: 'nbfc_groq_key',
} as const

const AdminContext = createContext<AdminContextValue | null>(null)

export function AdminProvider({ children }: { children: React.ReactNode }) {
  const [adminKey, _setAdminKey] = useState(() => localStorage.getItem(STORAGE.adminKey) ?? '')
  const [openrouterKey, _setOpenrouterKey] = useState(
    () => localStorage.getItem(STORAGE.openrouterKey) ?? '',
  )
  const [groqKey, _setGroqKey] = useState(() => localStorage.getItem(STORAGE.groqKey) ?? '')

  const setAdminKey = useCallback((v: string) => {
    localStorage.setItem(STORAGE.adminKey, v)
    _setAdminKey(v)
  }, [])

  const setOpenrouterKey = useCallback((v: string) => {
    localStorage.setItem(STORAGE.openrouterKey, v)
    _setOpenrouterKey(v)
  }, [])

  const setGroqKey = useCallback((v: string) => {
    localStorage.setItem(STORAGE.groqKey, v)
    _setGroqKey(v)
  }, [])

  return (
    <AdminContext.Provider
      value={{ adminKey, setAdminKey, openrouterKey, setOpenrouterKey, groqKey, setGroqKey }}
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
