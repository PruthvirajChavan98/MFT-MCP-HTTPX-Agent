// ── Barrel re-export ─────────────────────────────────────────────────────────
// All existing imports from '@features/admin/api/admin' continue to work.
// New code should import from the domain module directly.

export * from './faqs'
export * from './guardrails'
export * from './traces'
export * from './sessions'
export * from './health'
export * from './feedback'

// Re-export requestJson for backward compat (was exported at the bottom of the old monolith)
export { requestJson } from '@shared/api/http'
