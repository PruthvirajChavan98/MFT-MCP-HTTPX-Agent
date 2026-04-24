import { requestJson } from '@shared/api/http'

// ── Types ────────────────────────────────────────────────────────────────────

export interface AgentModelParameterSpec {
  name: string
  type?: string
  min?: number
  max?: number
  default?: string | number | boolean | null
  options?: string[]
}

export interface AgentModel {
  id: string
  name: string
  provider?: string
  display_name?: string
  is_reasoning_model?: boolean
  supports_reasoning_effort?: boolean
  supports_tools?: boolean
  supported_parameters?: string[]
  parameter_specs?: AgentModelParameterSpec[]
  type?: string
}

export interface AgentModelCategory {
  name: string
  models: AgentModel[]
}

export interface SystemHealthResponse {
  status: string
  healthy: boolean
  checks: Record<string, { ok: boolean; [key: string]: unknown }>
  timestamp: number
}

export interface RateLimitMetricsResponse {
  enabled: boolean
  message?: string
  metrics?: Record<string, Record<string, number>>
  timestamp?: number
}

export interface RateLimitConfigResponse {
  enabled: boolean
  algorithm: string
  failure_mode: string
  max_burst: number
  per_ip_enabled: boolean
  endpoints: Record<string, number>
  tiers: Record<string, number>
  per_ip: { enabled: boolean; limit: number }
}

// ── API ──────────────────────────────────────────────────────────────────────

export async function fetchModels(): Promise<AgentModelCategory[]> {
  const response = await requestJson<{
    categories: AgentModelCategory[]
  }>({ method: 'GET', path: '/agent/models' })
  return response.categories ?? []
}

export async function fetchSystemHealth(): Promise<SystemHealthResponse> {
  return requestJson({ method: 'GET', path: '/health/ready' })
}

export async function fetchRateLimitMetrics(): Promise<RateLimitMetricsResponse> {
  return requestJson({ method: 'GET', path: '/rate-limit/metrics' })
}

export async function fetchRateLimitConfig(): Promise<RateLimitConfigResponse> {
  return requestJson({ method: 'GET', path: '/rate-limit/config' })
}
