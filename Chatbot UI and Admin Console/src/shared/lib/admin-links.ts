export function buildConversationHref(sessionId?: string | null): string | null {
  const normalized = (sessionId || '').trim()
  if (!normalized) return null
  return `/admin/conversations?sessionId=${encodeURIComponent(normalized)}`
}

export function buildTraceHref(traceId?: string | null): string | null {
  const normalized = (traceId || '').trim()
  if (!normalized) return null
  return `/admin/traces?traceId=${encodeURIComponent(normalized)}`
}
