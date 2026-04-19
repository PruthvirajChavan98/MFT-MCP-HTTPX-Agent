import { requestJson } from '@/shared/api/http'

export interface IssueEnrollmentTokenRequest {
  email: string
  role?: 'admin' | 'super_admin'
  ttl_hours?: number
}

export interface IssueEnrollmentTokenResponse {
  token: string
  redeem_url: string
  email: string
  role: 'admin' | 'super_admin'
  expires_at: string
}

export interface EnrollmentTokenMetadata {
  email: string
  role: 'admin' | 'super_admin'
  expires_at: string
  status: 'pending' | 'consumed' | 'expired'
}

export interface RedeemEnrollmentTokenRequest {
  password: string
  totp_secret_base32: string
  totp_code: string
}

export interface RedeemEnrollmentTokenResponse {
  ok: boolean
  admin_id: string
}

export function issueEnrollmentToken(
  body: IssueEnrollmentTokenRequest,
): Promise<IssueEnrollmentTokenResponse> {
  return requestJson<IssueEnrollmentTokenResponse>({
    method: 'POST',
    path: '/agent/admin/enrollment/tokens',
    body,
  })
}

export function fetchEnrollmentTokenMetadata(
  plaintext: string,
): Promise<EnrollmentTokenMetadata> {
  return requestJson<EnrollmentTokenMetadata>({
    method: 'GET',
    path: `/agent/admin/enrollment/tokens/${encodeURIComponent(plaintext)}`,
  })
}

export function redeemEnrollmentToken(
  plaintext: string,
  body: RedeemEnrollmentTokenRequest,
): Promise<RedeemEnrollmentTokenResponse> {
  return requestJson<RedeemEnrollmentTokenResponse>({
    method: 'POST',
    path: `/agent/admin/enrollment/tokens/${encodeURIComponent(plaintext)}/redeem`,
    body,
  })
}

const BASE32_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'

/**
 * Generate a fresh 32-char base32 TOTP secret client-side.
 * Uses window.crypto for cryptographic randomness.
 */
export function generateTotpSecretBase32(length: number = 32): string {
  const bytes = new Uint8Array(length)
  window.crypto.getRandomValues(bytes)
  let out = ''
  for (let i = 0; i < length; i++) {
    out += BASE32_ALPHABET[bytes[i] % BASE32_ALPHABET.length]
  }
  return out
}
