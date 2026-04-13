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
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  path: string
  query?: Record<string, string | number | boolean | undefined | null>
  body?: unknown
  headers?: Record<string, string>
  signal?: AbortSignal
}

const CSRF_COOKIE_NAME = 'mft_admin_csrf'
const STATE_CHANGING_METHODS: ReadonlySet<RequestConfig['method']> = new Set([
  'POST',
  'PUT',
  'PATCH',
  'DELETE',
])

/**
 * Read a cookie value from document.cookie by name. Returns null when missing.
 * Used for CSRF double-submit — the httpOnly session cookies are invisible to
 * JS, but the CSRF cookie is set with `httpOnly: false` exactly so we can
 * read it here and echo it back in the X-CSRF-Token header.
 */
function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const prefix = `${name}=`
  const parts = document.cookie.split(';')
  for (const part of parts) {
    const trimmed = part.trim()
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length))
    }
  }
  return null
}

/**
 * Dispatched on any 401 response so app-level handlers (e.g. AdminAuthProvider)
 * can clear session state and redirect to the login page without every caller
 * needing to handle auth failures individually.
 */
export const ADMIN_SESSION_EXPIRED_EVENT = 'admin:session-expired'

export async function requestJson<T>(config: RequestConfig): Promise<T> {
  const csrfHeader: Record<string, string> = {}
  if (STATE_CHANGING_METHODS.has(config.method)) {
    const csrf = readCookie(CSRF_COOKIE_NAME)
    if (csrf) {
      csrfHeader['X-CSRF-Token'] = csrf
    }
  }

  const response = await fetch(`${joinPath(config.path)}${toQuery(config.query)}`, {
    method: config.method,
    credentials: 'include',
    headers: {
      ...(config.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...csrfHeader,
      ...(config.headers ?? {}),
    },
    body: config.body !== undefined ? JSON.stringify(config.body) : undefined,
    signal: config.signal,
  })

  const parsed = await parseBody(response)
  if (!response.ok) {
    const message = resolveErrorMessage(parsed, response.status)
    // Emit a session-expired signal on 401 so AdminAuthProvider can drop local
    // state and redirect to /admin/login. Individual callers still receive the
    // ApiError via the throw below.
    if (
      response.status === 401 &&
      typeof window !== 'undefined' &&
      !config.path.startsWith('/admin/auth/')
    ) {
      window.dispatchEvent(new CustomEvent(ADMIN_SESSION_EXPIRED_EVENT))
    }
    throw new ApiError(message, response.status, parsed)
  }

  return parsed as T
}
