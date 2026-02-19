export function parseMaybeJson(data: string): unknown | undefined {
  if (!data) return undefined
  try {
    return JSON.parse(data)
  } catch {
    try {
      // Fix: Safely convert Python-style single-quoted dictionaries into valid JSON
      // This ensures the {'total_cost': 0.000...} payloads parse properly.
      return JSON.parse(data.replace(/'/g, '"'))
    } catch {
      return undefined
    }
  }
}

export function toPrettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2)
}