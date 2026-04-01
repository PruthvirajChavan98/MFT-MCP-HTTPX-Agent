type RuntimeConfig = {
  API_BASE_URL?: string
  CRM_API_BASE_URL?: string
  APP_ENV?: string
  FEATURE_ADMIN_ENTERPRISE_REDESIGN?: string | boolean
  FEATURE_ADMIN_KNOWLEDGE_BASE_ENTERPRISE?: string | boolean
}

declare global {
  interface Window {
    __RUNTIME_CONFIG__?: RuntimeConfig
  }
}

const runtimeApiBase = window.__RUNTIME_CONFIG__?.API_BASE_URL?.trim()
export const API_BASE_URL = runtimeApiBase || '/api'
export const RUNTIME_CONFIG: RuntimeConfig = window.__RUNTIME_CONFIG__ ?? {}

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(message: string, status: number, detail: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function joinPath(path: string): string {
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

function toQuery(query?: Record<string, string | number | boolean | undefined | null>): string {
  if (!query) return ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue
    params.set(key, String(value))
  }
  const out = params.toString()
  return out ? `?${out}` : ''
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return undefined
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function resolveErrorMessage(parsed: unknown, status: number): string {
  if (typeof parsed === 'string' && parsed.trim()) return parsed
  if (typeof parsed !== 'object' || parsed === null) return `Request failed (${status})`

  const payload = parsed as {
    message?: string
    detail?: string | { message?: string; detail?: string }
  }
  if (typeof payload.message === 'string' && payload.message.trim()) return payload.message.trim()
  if (typeof payload.detail === 'string' && payload.detail.trim()) return payload.detail.trim()
  if (payload.detail && typeof payload.detail === 'object') {
    if (
      typeof payload.detail.message === 'string' &&
      payload.detail.message.trim()
    ) {
      return payload.detail.message.trim()
    }
    if (
      typeof payload.detail.detail === 'string' &&
      payload.detail.detail.trim()
    ) {
      return payload.detail.detail.trim()
    }
  }
  return `Request failed (${status})`
}

interface RequestConfig {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  path: string
  query?: Record<string, string | number | boolean | undefined | null>
  body?: unknown
  headers?: Record<string, string>
  signal?: AbortSignal
}

export async function requestJson<T>(config: RequestConfig): Promise<T> {
  const response = await fetch(`${joinPath(config.path)}${toQuery(config.query)}`, {
    method: config.method,
    headers: {
      ...(config.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(config.headers ?? {}),
    },
    body: config.body !== undefined ? JSON.stringify(config.body) : undefined,
    signal: config.signal,
  })

  const parsed = await parseBody(response)
  if (!response.ok) {
    const message = resolveErrorMessage(parsed, response.status)
    throw new ApiError(message, response.status, parsed)
  }

  return parsed as T
}

export function withAdminHeaders(
  adminKey?: string,
  extra?: Record<string, string>,
): Record<string, string> {
  const headers: Record<string, string> = { ...(extra ?? {}) }
  if (adminKey?.trim()) {
    headers['X-Admin-Key'] = adminKey.trim()
  }
  return headers
}
