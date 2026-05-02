/**
 * Per-service rows extracted from compose.yaml at the repo root.
 * Used by the topology section's <details> table — values lifted, not invented.
 */

export interface ComposeService {
  name: string
  image: string
  port: string
  network: string
  role: string
}

export const COMPOSE_SERVICES: readonly ComposeService[] = [
  {
    name: 'cloudflared-prod',
    image: 'cloudflare/cloudflared:latest',
    port: '—',
    network: 'mft_net',
    role: 'Cloudflare tunnel — public ingress for two hostnames',
  },
  {
    name: 'frontend-prod',
    image: 'mft_frontend_prod:latest',
    port: '80',
    network: 'mft_net + databases',
    role: 'Nginx + built React assets, edge L7 defense, SSE proxy',
  },
  {
    name: 'agent',
    image: 'mft_agent:latest',
    port: '8000',
    network: 'mft_net + databases',
    role: 'FastAPI app — LangGraph supervisor, REST/SSE, admin APIs',
  },
  {
    name: 'mcp',
    image: 'mft_mcp:latest',
    port: '8050',
    network: 'mft_net + databases',
    role: 'FastMCP server — 14 tools, separate process from agent',
  },
  {
    name: 'shadow_judge_worker',
    image: 'mft_shadow_judge:latest',
    port: '—',
    network: 'mft_net + databases',
    role: 'Consumes trace queue, scores Helpfulness/Faithfulness/Policy',
  },
  {
    name: 'geoip_updater',
    image: 'mft_agent (reused)',
    port: '—',
    network: 'mft_net',
    role: 'Daily refresh of GeoIP / Tor exit-node lists',
  },
  {
    name: 'db-migrate',
    image: 'postgres:18.3-bookworm',
    port: '—',
    network: 'databases',
    role: 'Idempotent schema bootstrap (init container)',
  },
  {
    name: 'prometheus',
    image: 'prom/prometheus:v2.53.1',
    port: '9090',
    network: 'mft_net',
    role: 'Scrapes agent metrics endpoint',
  },
  {
    name: 'alertmanager',
    image: 'prom/alertmanager:v0.28.0',
    port: '9093',
    network: 'mft_net',
    role: 'Alert routing for Prometheus rules',
  },
  {
    name: 'grafana',
    image: 'grafana/grafana:11.1.4',
    port: '3000',
    network: 'mft_net',
    role: 'Dashboards over Prometheus + Postgres',
  },
] as const
