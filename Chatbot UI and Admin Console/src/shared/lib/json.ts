export function parseMaybeJson(data: string): unknown | undefined {
  if (!data) return undefined
  try {
    return JSON.parse(data)
  } catch {
    return undefined
  }
}

export function toPrettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2)
}
