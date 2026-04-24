import { requestJson } from '@shared/api/http'

// ── Admin users (enrollment + revocation) ──────────────────────────────────
//
// Super-admin-only endpoints. `requestJson` already threads the JWT cookie
// and the X-CSRF-Token header; mutating calls here reuse that helper.

export interface AdminUser {
  id: string
  email: string
  is_super_admin: boolean
  created_at: string
  created_by_admin_id: string | null
}

export interface CreateAdminResult extends AdminUser {
  /** Raw base32 TOTP secret — shown ONCE on creation, never re-fetchable. */
  totp_secret_base32: string
  /** otpauth:// provisioning URI for QR rendering, same one-time-only rule. */
  otpauth_uri: string
}

export async function listAdmins(): Promise<AdminUser[]> {
  const response = await requestJson<{ items: AdminUser[] }>({
    method: 'GET',
    path: '/agent/admin/admins',
  })
  return response.items ?? []
}

export async function createAdmin(payload: {
  email: string
  password: string
}): Promise<CreateAdminResult> {
  return requestJson<CreateAdminResult>({
    method: 'POST',
    path: '/agent/admin/admins',
    body: payload,
  })
}

export async function revokeAdmin(id: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>({
    method: 'DELETE',
    path: `/agent/admin/admins/${encodeURIComponent(id)}`,
  })
}
