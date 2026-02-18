export function extractPathTokens(path: string): string[] {
  return [...path.matchAll(/\{([^}]+)\}/g)].map((match) => match[1])
}

export function resolvePath(pathTemplate: string, pathParams: Record<string, unknown>): string {
  return pathTemplate.replace(/\{([^}]+)\}/g, (_full, key: string) => {
    const value = pathParams[key]
    if (value === undefined || value === null || String(value).trim() === '') {
      throw new Error(`Missing required path param: ${key}`)
    }
    return encodeURIComponent(String(value))
  })
}

export function toQueryString(query: Record<string, unknown>): string {
  const params = new URLSearchParams()

  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === '') continue

    if (Array.isArray(value)) {
      for (const item of value) {
        params.append(key, String(item))
      }
      continue
    }

    if (typeof value === 'object') {
      params.append(key, JSON.stringify(value))
      continue
    }

    params.append(key, String(value))
  }

  const serialized = params.toString()
  return serialized ? `?${serialized}` : ''
}
