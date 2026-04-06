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

/**
 * RFC 7807 Problem Details for HTTP APIs + FastAPI error shape support.
 *
 * Extraction priority:
 * 1. RFC 7807 `title` / `detail` fields (standardised)
 * 2. FastAPI `detail` string (default HTTPException shape)
 * 3. Generic `message` / `error` fields (common REST conventions)
 * 4. Fallback to status code
 */
interface ProblemDetails {
  type?: string
  title?: string
  status?: number
  detail?: string | { message?: string; detail?: string }
  instance?: string
  message?: string
  error?: string
}

function resolveErrorMessage(parsed: unknown, status: number): string {
  if (typeof parsed === 'string' && parsed.trim()) return parsed
  if (typeof parsed !== 'object' || parsed === null) return `Request failed (${status})`

  const p = parsed as ProblemDetails

  // RFC 7807: prefer `title` for short user-facing messages, `detail` for specifics
  if (typeof p.title === 'string' && p.title.trim()) return p.title.trim()
  if (typeof p.detail === 'string' && p.detail.trim()) return p.detail.trim()
  // FastAPI nested detail object
  if (p.detail && typeof p.detail === 'object') {
    const nested = p.detail
    if (typeof nested.message === 'string' && nested.message.trim()) return nested.message.trim()
    if (typeof nested.detail === 'string' && nested.detail.trim()) return nested.detail.trim()
  }
  // Common REST conventions
  if (typeof p.message === 'string' && p.message.trim()) return p.message.trim()
  if (typeof p.error === 'string' && p.error.trim()) return p.error.trim()

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
