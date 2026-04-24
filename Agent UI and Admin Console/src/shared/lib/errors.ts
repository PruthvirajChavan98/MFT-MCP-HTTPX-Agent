/**
 * Extract a user-visible message from an unknown error value.
 *
 * - `Error` instances yield their `message` (when non-blank).
 * - Bare strings pass through (when non-blank).
 * - Anything else falls back to a generic "Request failed" string.
 */
export function getErrorMessage(err: unknown): string {
  if (err instanceof Error && err.message.trim()) return err.message
  if (typeof err === 'string' && err.trim()) return err
  return 'Request failed'
}
