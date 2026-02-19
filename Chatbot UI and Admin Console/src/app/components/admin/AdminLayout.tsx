import { useCallback, useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import {
  BadgeDollarSign,
  Database,
  Eye,
  EyeOff,
  GitBranch,
  LayoutDashboard,
  MessageSquare,
  Settings,
  ShieldAlert,
  Tags,
  ThumbsUp,
  Users,
} from 'lucide-react'
import { AdminProvider, useAdminContext } from './AdminContext'
import { CommandPalette } from './CommandPalette'

const NAV = [
  { path: '/admin', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { path: '/admin/knowledge-base', label: 'Knowledge Base', icon: Database },
  { path: '/admin/costs', label: 'Costs', icon: BadgeDollarSign },
  { path: '/admin/traces', label: 'Traces', icon: GitBranch },
  { path: '/admin/categories', label: 'Categories', icon: Tags },
  { path: '/admin/conversations', label: 'Conversations', icon: MessageSquare },
  { path: '/admin/model-config', label: 'Model Config', icon: Settings },
  { path: '/admin/guardrails', label: 'Guardrails', icon: ShieldAlert },
  { path: '/admin/users', label: 'Users', icon: Users },
  { path: '/admin/feedback', label: 'Feedback', icon: ThumbsUp },
] as const satisfies Array<{ path: string; label: string; icon: React.ElementType; end?: boolean }>

function KeyInput({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  const [visible, setVisible] = useState(false)
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-600 min-w-0">
      <span className="font-semibold truncate">{label}</span>
      <div className="relative">
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={`Set ${label}`}
          className="w-full rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 pr-7 text-xs focus:outline-none focus:ring-2 focus:ring-cyan-400 transition"
        />
        <button
          type="button"
          onClick={() => setVisible((p) => !p)}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
        >
          {visible ? <EyeOff size={13} /> : <Eye size={13} />}
        </button>
      </div>
    </label>
  )
}

function AdminShell() {
  const auth = useAdminContext()
  const [cmdOpen, setCmdOpen] = useState(false)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCmdOpen((p) => !p)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="hidden lg:flex flex-col w-64 shrink-0 border-r border-slate-800 bg-slate-950 text-slate-100">
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-5 border-b border-slate-800">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-teal-500 flex items-center justify-center font-bold text-white text-sm">
            TF
          </div>
          <div>
            <p className="text-sm font-semibold text-cyan-100 leading-tight">TrustFin Admin</p>
            <p className="text-xs text-slate-400">Production Console</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV.map((item: any) => {
            const { path, label, icon: Icon, end } = item
            return (
              <NavLink
                key={path}
                to={path}
                end={end}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${isActive
                    ? 'bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-400/30'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'
                  }`
                }
              >
                <Icon size={16} />
                <span>{label}</span>
              </NavLink>
            )
          })}
        </nav>

        {/* CMD+K hint */}
        <div className="px-5 py-3 border-t border-slate-800">
          <button
            onClick={() => setCmdOpen(true)}
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-slate-800 text-xs text-slate-400 hover:bg-slate-700 transition-colors"
          >
            <span>Quick navigate</span>
            <kbd className="px-1.5 py-0.5 rounded bg-slate-700 text-slate-300 font-mono text-[10px]">
              ⌘K
            </kbd>
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Key header */}
        <header className="border-b border-slate-200 bg-white px-6 py-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-3xl">
            <KeyInput label="X-Admin-Key" value={auth.adminKey} onChange={auth.setAdminKey} />
            <KeyInput
              label="X-OpenRouter-Key"
              value={auth.openrouterKey}
              onChange={auth.setOpenrouterKey}
            />
            <KeyInput label="X-Groq-Key" value={auth.groqKey} onChange={auth.setGroqKey} />
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>

      <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} />
    </div >
  )
}

export function AdminLayout() {
  return (
    <AdminProvider>
      <AdminShell />
    </AdminProvider>
  )
}
