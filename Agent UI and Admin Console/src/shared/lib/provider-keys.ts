import type { SessionConfig } from '@shared/api/sessions'

/**
 * Returns `true` when the given provider requires the user to supply a
 * session-level API key before inference can proceed.
 */
export function providerRequiresSessionKey(provider: string): boolean {
  return provider === 'openrouter' || provider === 'nvidia'
}

/**
 * Checks whether the backend already stores a provider key for the given
 * provider within the supplied session config.
 */
export function hasSavedProviderKey(
  provider: string,
  sessionCfg?: SessionConfig,
): boolean {
  if (provider === 'openrouter') return !!sessionCfg?.has_openrouter_key
  if (provider === 'nvidia') return !!sessionCfg?.has_nvidia_key
  if (provider === 'groq') return !!sessionCfg?.has_groq_key
  return false
}
