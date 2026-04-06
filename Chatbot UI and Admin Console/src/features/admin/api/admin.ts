/**
 * @deprecated This barrel file is a backward-compatibility shim.
 * New code should import from the domain module directly
 * (e.g. `@features/admin/api/faqs`, `@features/admin/api/traces`, etc.).
 */

export * from './faqs'
export * from './guardrails'
export * from './traces'
export * from './sessions'
export * from './health'
export * from './feedback'

// Re-export requestJson for backward compat (was exported at the bottom of the old monolith)
export { requestJson } from '@shared/api/http'
