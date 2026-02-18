import { A, useLocation } from '@solidjs/router'
import type { RouteSectionProps } from '@solidjs/router'

interface NavItem {
  path: string
  label: string
  blurb: string
}

const NAV_ITEMS: NavItem[] = [
  { path: '/', label: 'Overview', blurb: 'Platform telemetry + quick launch' },
  { path: '/chat', label: 'Chat', blurb: 'Conversational agent with streaming' },
  { path: '/workbench', label: 'Workbench', blurb: 'All API endpoints in one console' },
  { path: '/operations', label: 'Operations', blurb: 'Health, eval, rate-limit, graphql' },
  { path: '/streams', label: 'Streams', blurb: 'SSE-first execution and diagnostics' },
  { path: '/admin', label: 'Admin', blurb: 'FAQ and admin controls' },
]

export function AppShell(props: RouteSectionProps) {
  const location = useLocation()

  return (
    <div class="shell">
      <aside class="nav-rail">
        <div class="brand-block">
          <p class="brand-kicker">MFT Platform</p>
          <h1>Enterprise Agent Console</h1>
          <p>Production-grade control surface for backend APIs, streams, and ops telemetry.</p>
        </div>

        <nav class="rail-links" aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const active = () => (item.path === '/' ? location.pathname === '/' : location.pathname.startsWith(item.path))
            return (
              <A href={item.path} class={`rail-link ${active() ? 'active' : ''}`}>
                <span>{item.label}</span>
                <small>{item.blurb}</small>
              </A>
            )
          })}
        </nav>

        <div class="rail-foot">
          <div>
            <span>Theme</span>
            <strong>Brand OKLCH</strong>
          </div>
          <div>
            <span>Proxy</span>
            <strong>/api to backend</strong>
          </div>
        </div>
      </aside>

      <main class="shell-main">{props.children}</main>
    </div>
  )
}
