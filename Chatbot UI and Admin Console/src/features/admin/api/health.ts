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

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- untyped backend response; type properly when API schema is available
export async function fetchRateLimitMetrics(): Promise<any> {
  return requestJson({ method: 'GET', path: '/rate-limit/metrics' })
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- untyped backend response; type properly when API schema is available
export async function fetchRateLimitConfig(): Promise<any> {
  return requestJson({ method: 'GET', path: '/rate-limit/config' })
}
