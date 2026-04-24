import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as adminsApi from '@features/admin/api/admins'
import { MfaPromptContext } from '@features/admin/auth/MfaPromptProvider'
import { AdminUsersCreateModal } from './AdminUsersCreateModal'

function wrap(ui: React.ReactNode) {
  return (
    <MfaPromptContext.Provider
      value={{
        promptMfa: () => Promise.resolve(),
      }}
    >
      {ui}
    </MfaPromptContext.Provider>
  )
}

describe('AdminUsersCreateModal', () => {
  beforeEach(() => {
    // Ensure crypto.randomUUID / getRandomValues exist in JSDOM for
    // the "generate password" button.
    if (!('getRandomValues' in globalThis.crypto)) {
      Object.defineProperty(globalThis.crypto, 'getRandomValues', {
        value: (buf: Uint8Array) => {
          for (let i = 0; i < buf.length; i++) buf[i] = i % 256
          return buf
        },
      })
    }
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('validates email and password before calling createAdmin', async () => {
    const spy = vi.spyOn(adminsApi, 'createAdmin')

    render(
      wrap(
        <AdminUsersCreateModal
          open
          created={null}
          onSuccess={() => {}}
          onClose={() => {}}
        />,
      ),
    )

    fireEvent.click(screen.getByRole('button', { name: /create admin/i }))

    expect(spy).not.toHaveBeenCalled()
    expect(screen.getByText('Enter a valid email address')).toBeTruthy()
    expect(screen.getByText('Password must be at least 12 characters')).toBeTruthy()
  })

  it('calls createAdmin with trimmed lowercased email', async () => {
    const onSuccess = vi.fn()
    const spy = vi.spyOn(adminsApi, 'createAdmin').mockResolvedValue({
      id: 'new-id',
      email: 'someone@example.com',
      is_super_admin: false,
      created_at: '2026-04-17T13:00:00Z',
      created_by_admin_id: 'self-id',
      totp_secret_base32: 'JBSWY3DPEHPK3PXP',
      otpauth_uri:
        'otpauth://totp/mft-agent-admin:someone%40example.com?secret=JBSWY3DPEHPK3PXP&issuer=mft-agent-admin',
    })

    render(
      wrap(
        <AdminUsersCreateModal
          open
          created={null}
          onSuccess={onSuccess}
          onClose={() => {}}
        />,
      ),
    )

    fireEvent.change(screen.getByPlaceholderText('new-admin@example.com'), {
      target: { value: '  Someone@Example.com  ' },
    })
    fireEvent.change(screen.getByPlaceholderText('Minimum 12 characters'), {
      target: { value: 'another-strong-pw' },
    })
    fireEvent.click(screen.getByRole('button', { name: /create admin/i }))

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    expect(spy).toHaveBeenCalledWith({
      email: 'someone@example.com',
      password: 'another-strong-pw',
    })
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1))
  })

  it('shows one-time secret pane with copy buttons after successful create', async () => {
    const created = {
      id: 'new-id',
      email: 'someone@example.com',
      is_super_admin: false,
      created_at: '2026-04-17T13:00:00Z',
      created_by_admin_id: 'self-id',
      totp_secret_base32: 'JBSWY3DPEHPK3PXP',
      otpauth_uri:
        'otpauth://totp/mft-agent-admin:someone%40example.com?secret=JBSWY3DPEHPK3PXP&issuer=mft-agent-admin',
    }

    render(
      wrap(
        <AdminUsersCreateModal
          open
          created={created}
          onSuccess={() => {}}
          onClose={() => {}}
        />,
      ),
    )

    expect(screen.getByText(/One-time credentials/)).toBeTruthy()
    expect(screen.getByText('someone@example.com')).toBeTruthy()
    // Secret is rendered inside a read-only input, not as text
    expect(
      (screen.getByDisplayValue('JBSWY3DPEHPK3PXP') as HTMLInputElement).readOnly,
    ).toBe(true)
    expect(screen.getByDisplayValue(created.otpauth_uri)).toBeTruthy()
    // Three copy buttons — accessible-name comes from the aria-label attribute
    // applied in Phase 2 hardening.
    expect(screen.getByRole('button', { name: 'Copy Initial password' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Copy TOTP secret (base32)' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Copy TOTP otpauth URI' })).toBeTruthy()
  })

  it('warns on close when secret has not been copied', () => {
    const onClose = vi.fn()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

    const created = {
      id: 'new-id',
      email: 'someone@example.com',
      is_super_admin: false,
      created_at: '2026-04-17T13:00:00Z',
      created_by_admin_id: 'self-id',
      totp_secret_base32: 'JBSWY3DPEHPK3PXP',
      otpauth_uri:
        'otpauth://totp/mft-agent-admin:someone%40example.com?secret=JBSWY3DPEHPK3PXP&issuer=mft-agent-admin',
    }

    render(
      wrap(
        <AdminUsersCreateModal
          open
          created={created}
          onSuccess={() => {}}
          onClose={onClose}
        />,
      ),
    )

    fireEvent.click(screen.getByLabelText('Close dialog'))
    expect(confirmSpy).toHaveBeenCalledWith(
      expect.stringContaining('will not be shown again'),
    )
    expect(onClose).not.toHaveBeenCalled() // user declined
  })
})
