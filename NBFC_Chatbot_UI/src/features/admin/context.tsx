import { type Accessor, type JSX, createContext, createEffect, createSignal, useContext } from 'solid-js'

interface AdminContextValue {
  adminKey: Accessor<string>
  setAdminKey: (value: string) => void
  openrouterKey: Accessor<string>
  setOpenrouterKey: (value: string) => void
  groqKey: Accessor<string>
  setGroqKey: (value: string) => void
}

const STORAGE = {
  adminKey: 'nbfc_admin_key',
  openrouterKey: 'nbfc_openrouter_key',
  groqKey: 'nbfc_groq_key',
}

const AdminContext = createContext<AdminContextValue>()

export function AdminProvider(props: { children: JSX.Element }) {
  const [adminKey, setAdminKey] = createSignal(localStorage.getItem(STORAGE.adminKey) ?? '')
  const [openrouterKey, setOpenrouterKey] = createSignal(localStorage.getItem(STORAGE.openrouterKey) ?? '')
  const [groqKey, setGroqKey] = createSignal(localStorage.getItem(STORAGE.groqKey) ?? '')

  createEffect(() => {
    localStorage.setItem(STORAGE.adminKey, adminKey())
  })

  createEffect(() => {
    localStorage.setItem(STORAGE.openrouterKey, openrouterKey())
  })

  createEffect(() => {
    localStorage.setItem(STORAGE.groqKey, groqKey())
  })

  return (
    <AdminContext.Provider
      value={{ adminKey, setAdminKey, openrouterKey, setOpenrouterKey, groqKey, setGroqKey }}
    >
      {props.children}
    </AdminContext.Provider>
  )
}

export function useAdminAuth() {
  const ctx = useContext(AdminContext)
  if (!ctx) {
    throw new Error('useAdminAuth must be used inside AdminProvider')
  }
  return ctx
}
