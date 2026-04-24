// ── Re-export from shared navigation (backward compat) ──────────────────────
// New code should import from '@shared/lib/navigation' directly.

export {
  buildConversationHref,
  buildTraceHref,
  clearTraceIdSearchParams,
  setTraceIdSearchParams,
} from '@shared/lib/navigation'
