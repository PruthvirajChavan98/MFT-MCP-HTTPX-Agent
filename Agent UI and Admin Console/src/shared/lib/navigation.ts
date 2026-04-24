// ── Navigation helpers shared across features ────────────────────────────────

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

export function clearTraceIdSearchParams(searchParams: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(searchParams)
  next.delete('traceId')
  return next
}

export function setTraceIdSearchParams(
  searchParams: URLSearchParams,
  traceId?: string | null,
): URLSearchParams {
  const next = new URLSearchParams(searchParams)
  const normalized = (traceId || '').trim()
  if (normalized) next.set('traceId', normalized)
  else next.delete('traceId')
  return next
}
