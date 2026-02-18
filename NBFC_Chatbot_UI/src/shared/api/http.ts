export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

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
    const message =
      typeof parsed === 'string'
        ? parsed
        : (parsed as { detail?: string })?.detail ?? `Request failed (${response.status})`
    throw new ApiError(message, response.status, parsed)
  }

  return parsed as T
}

export function withAdminHeaders(adminKey?: string, extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...(extra ?? {}) }
  if (adminKey?.trim()) {
    headers['X-Admin-Key'] = adminKey.trim()
  }
  return headers
}
