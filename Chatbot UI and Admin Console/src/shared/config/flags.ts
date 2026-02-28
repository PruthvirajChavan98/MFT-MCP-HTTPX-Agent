import { RUNTIME_CONFIG } from '../api/http'

function parseBoolean(value: string | boolean | undefined, fallback = false): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value !== 'string') return fallback

  const normalized = value.trim().toLowerCase()
  if (!normalized) return fallback
  if (['1', 'true', 'yes', 'y', 'on'].includes(normalized)) return true
  if (['0', 'false', 'no', 'n', 'off'].includes(normalized)) return false
  return fallback
}

export const flags = {
  adminEnterpriseRedesign: parseBoolean(RUNTIME_CONFIG.FEATURE_ADMIN_ENTERPRISE_REDESIGN, false),
  adminKnowledgeBaseEnterprise: parseBoolean(
    RUNTIME_CONFIG.FEATURE_ADMIN_KNOWLEDGE_BASE_ENTERPRISE,
    false,
  ),
} as const
