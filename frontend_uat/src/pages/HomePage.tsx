import { A } from '@solidjs/router'
import { For } from 'solid-js'
import { ENDPOINTS } from '../config/endpoints'
import { PageHeader } from '../components/layout/PageHeader'

interface CategoryMetric {
  category: string
  count: number
}

const categoryMetrics: CategoryMetric[] = Object.entries(
  ENDPOINTS.reduce<Record<string, number>>((acc, endpoint) => {
    acc[endpoint.category] = (acc[endpoint.category] ?? 0) + 1
    return acc
  }, {}),
)
  .map(([category, count]) => ({ category, count }))
  .sort((a, b) => b.count - a.count)

const quickLinks = [
  { href: '/workbench', title: 'Full Workbench', copy: 'Single-pane execution surface for every API route.' },
  { href: '/streams', title: 'Streaming Studio', copy: 'SSE-heavy flows with reasoning/token and event trace view.' },
  { href: '/operations', title: 'Operations', copy: 'Health, eval, rate limit, and GraphQL operational controls.' },
  { href: '/admin', title: 'Admin', copy: 'FAQ curation and admin-only backend operations.' },
]

export function HomePage() {
  return (
    <div class="page-stack">
      <PageHeader
        title="MFT Frontend Control Plane"
        subtitle="Enterprise Multi-Page Architecture"
        rightLabel="Endpoint Coverage"
        rightValue={String(ENDPOINTS.length)}
      />

      <section class="card intro-grid">
        <article>
          <h3>Why this structure</h3>
          <p>
            This frontend is split into routed pages, reusable modules, and a centralized endpoint registry. It is designed
            for long-term maintainability, operability, and production evolution.
          </p>
        </article>
        <article>
          <h3>Brand theme</h3>
          <p>
            Color system is built from your OKLCH brand spectrum and applied across surface layers, accent gradients, and
            interaction states.
          </p>
        </article>
      </section>

      <section class="dashboard-grid">
        <For each={quickLinks}>
          {(item) => (
            <A href={item.href} class="card quick-link">
              <h3>{item.title}</h3>
              <p>{item.copy}</p>
              <span>Open</span>
            </A>
          )}
        </For>
      </section>

      <section class="card">
        <div class="panel-head">
          <h3>Endpoint Distribution</h3>
          <p>All mounted backend domains represented in the FE registry.</p>
        </div>
        <div class="metric-grid">
          <For each={categoryMetrics}>
            {(metric) => (
              <article class="metric-item">
                <strong>{metric.count}</strong>
                <span>{metric.category}</span>
              </article>
            )}
          </For>
        </div>
      </section>
    </div>
  )
}
