import { A, useLocation } from '@solidjs/router'
import {
  BadgeDollarSign,
  Database,
  GitBranch,
  LayoutDashboard,
  MessageSquare,
  Settings,
  ShieldAlert,
  Tags,
  ThumbsUp,
  Users,
} from 'lucide-solid'
import { type JSX, For } from 'solid-js'
import { AdminProvider, useAdminAuth } from '../../features/admin/context'
import BrainIcon from '../../shared/ui/BrainIcon'

interface NavItem {
  path: string
  label: string
  icon: () => JSX.Element
}

function AdminShell(props: { children?: JSX.Element }) {
  const location = useLocation()
  const auth = useAdminAuth()

  const nav: NavItem[] = [
    { path: '/admin', label: 'Dashboard', icon: () => <LayoutDashboard size={16} /> },
    { path: '/admin/knowledge-base', label: 'Knowledge Base', icon: () => <Database size={16} /> },
    { path: '/admin/costs', label: 'Costs', icon: () => <BadgeDollarSign size={16} /> },
    { path: '/admin/traces', label: 'Traces', icon: () => <GitBranch size={16} /> },
    { path: '/admin/categories', label: 'Categories', icon: () => <Tags size={16} /> },
    { path: '/admin/conversations', label: 'Conversations', icon: () => <MessageSquare size={16} /> },
    { path: '/admin/model-config', label: 'Model Config', icon: () => <Settings size={16} /> },
    { path: '/admin/guardrails', label: 'Guardrails', icon: () => <ShieldAlert size={16} /> },
    { path: '/admin/users', label: 'Users', icon: () => <Users size={16} /> },
    { path: '/admin/feedback', label: 'Feedback', icon: () => <ThumbsUp size={16} /> },
  ]

  const active = (path: string) => location.pathname === path

  return (
    <div class="grid min-h-screen grid-cols-1 lg:grid-cols-[280px_1fr]">
      <aside class="border-r border-cyan-100 bg-slate-950 p-5 text-slate-100">
        <div class="mb-8 flex items-center gap-3">
          <BrainIcon size={54} />
          <div>
            <p class="text-sm font-semibold text-cyan-100">TrustFin Admin</p>
            <p class="text-xs text-slate-400">Production Console</p>
          </div>
        </div>

        <nav class="space-y-1">
          <For each={nav}>
            {(item) => (
              <A
                href={item.path}
                class={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${
                  active(item.path)
                    ? 'bg-cyan-500/20 text-cyan-100 ring-1 ring-cyan-400/30'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                {item.icon()}
                <span>{item.label}</span>
              </A>
            )}
          </For>
        </nav>
      </aside>

      <main class="p-4 sm:p-6 lg:p-8">
        <header class="mb-5 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-3">
          <label class="text-xs text-slate-600">
            <span class="mb-1 block font-semibold">X-Admin-Key</span>
            <input
              value={auth.adminKey()}
              onInput={(event) => auth.setAdminKey(event.currentTarget.value)}
              type="password"
              class="input-base w-full"
              placeholder="Set admin API key"
            />
          </label>

          <label class="text-xs text-slate-600">
            <span class="mb-1 block font-semibold">X-OpenRouter-Key</span>
            <input
              value={auth.openrouterKey()}
              onInput={(event) => auth.setOpenrouterKey(event.currentTarget.value)}
              type="password"
              class="input-base w-full"
              placeholder="Optional for FAQ vector ops"
            />
          </label>

          <label class="text-xs text-slate-600">
            <span class="mb-1 block font-semibold">X-Groq-Key</span>
            <input
              value={auth.groqKey()}
              onInput={(event) => auth.setGroqKey(event.currentTarget.value)}
              type="password"
              class="input-base w-full"
              placeholder="Optional for FAQ ingest"
            />
          </label>
        </header>

        {props.children}
      </main>
    </div>
  )
}

export default function AdminLayout(props: { children?: JSX.Element }) {
  return (
    <AdminProvider>
      <AdminShell>{props.children}</AdminShell>
    </AdminProvider>
  )
}
