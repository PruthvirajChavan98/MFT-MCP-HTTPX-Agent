import { requestJson } from './http'

// ── Types ────────────────────────────────────────────────────────────────────

export interface SessionConfig {
  session_id: string
  system_prompt?: string
  model_name?: string
  reasoning_effort?: string
  provider?: string
  has_openrouter_key?: boolean
  has_nvidia_key?: boolean
  has_groq_key?: boolean
}

// ── API ──────────────────────────────────────────────────────────────────────

export async function fetchSessionConfig(sessionId: string): Promise<SessionConfig> {
  return requestJson({
    method: 'GET',
    path: `/agent/config/${encodeURIComponent(sessionId)}`,
  })
}

export async function saveSessionConfig(payload: {
  session_id: string
  system_prompt?: string
  model_name?: string
  reasoning_effort?: string
  provider?: string
  openrouter_api_key?: string
  nvidia_api_key?: string
  groq_api_key?: string
}): Promise<{ status: string }> {
  return requestJson({ method: 'POST', path: '/agent/config', body: payload })
}
