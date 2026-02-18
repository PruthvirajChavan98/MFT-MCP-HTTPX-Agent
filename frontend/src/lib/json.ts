export function parseObjectJson(source: string, contextLabel: string): Record<string, unknown> {
  const value = source.trim() ? JSON.parse(source) : {}

  if (value === null || Array.isArray(value) || typeof value !== 'object') {
    throw new Error(`${contextLabel} must be a JSON object`)
  }

  return value as Record<string, unknown>
}

export function formatPretty(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

export function parseMaybeJson(data: string): unknown | undefined {
  try {
    return JSON.parse(data)
  } catch {
    return undefined
  }
}

export function cleanHeaderValues(raw: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {}

  for (const [key, value] of Object.entries(raw)) {
    if (!key.trim()) continue
    if (value === null || value === undefined) continue
    const text = String(value).trim()
    if (!text) continue
    out[key] = text
  }

  return out
}
