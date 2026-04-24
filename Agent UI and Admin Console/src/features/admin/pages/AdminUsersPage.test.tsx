import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as adminsApi from '@features/admin/api/admins'
import { MfaPromptContext } from '@features/admin/auth/MfaPromptProvider'

// Mutable session stub — tests can override the roles to exercise the
// client-side role guard added in Phase 2 hardening (S-M4).
const mockSession = {
  current: {
    sub: 'self-id',
    email: 'me@example.com',
    roles: ['admin', 'super_admin'] as readonly string[],
    mfa_fresh: true,
    exp: 9_999_999_999,
  },
}

vi.mock('@features/admin/auth/AdminAuthProvider', () => ({
  useAdminAuth: () => ({ session: mockSession.current }),
}))

function withProviders(ui: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  })
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <MfaPromptContext.Provider
          value={{
            promptMfa: () => Promise.resolve(),
          }}
        >
          {ui}
        </MfaPromptContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

// Import AFTER the mocks so vi.mock takes effect.
async function loadPage() {
  const module = await import('./AdminUsersPage')
  return module.AdminUsersPage
}

describe('AdminUsersPage', () => {
  beforeEach(() => {
    // Reset to super-admin session before each test so the guard test can
    // downgrade without leaking into other tests.
    mockSession.current = {
      sub: 'self-id',
      email: 'me@example.com',
      roles: ['admin', 'super_admin'] as readonly string[],
      mfa_fresh: true,
      exp: 9_999_999_999,
    }
    vi.spyOn(adminsApi, 'listAdmins').mockResolvedValue([
      {
        id: 'self-id',
        email: 'me@example.com',
        is_super_admin: true,
        created_at: '2026-04-17T12:00:00Z',
        created_by_admin_id: null,
      },
      {
        id: 'other-id',
        email: 'plain@example.com',
        is_super_admin: false,
        created_at: '2026-04-17T13:00:00Z',
        created_by_admin_id: 'self-id',
      },
    ])
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders the active admins with role badges and self marker', async () => {
    const AdminUsersPage = await loadPage()
    render(withProviders(<AdminUsersPage />))

    await waitFor(() =>
      expect(screen.getByText('me@example.com')).toBeTruthy(),
    )
    expect(screen.getByText('plain@example.com')).toBeTruthy()
    // "you" chip shown next to the caller's own row
    expect(screen.getByText('you')).toBeTruthy()
    expect(screen.getByText('super admin')).toBeTruthy()
    expect(screen.getByText('admin')).toBeTruthy()
  })

  it('disables the revoke button on the caller’s own row', async () => {
    const AdminUsersPage = await loadPage()
    render(withProviders(<AdminUsersPage />))

    await waitFor(() => screen.getByText('me@example.com'))
    const selfButton = screen.getByLabelText('Revoke me@example.com') as HTMLButtonElement
    const otherButton = screen.getByLabelText('Revoke plain@example.com') as HTMLButtonElement
    expect(selfButton.disabled).toBe(true)
    expect(otherButton.disabled).toBe(false)
  })

  it('calls revokeAdmin when confirmed', async () => {
    const revokeSpy = vi
      .spyOn(adminsApi, 'revokeAdmin')
      .mockResolvedValue({ ok: true })
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    const AdminUsersPage = await loadPage()
    render(withProviders(<AdminUsersPage />))

    await waitFor(() => screen.getByText('plain@example.com'))
    fireEvent.click(screen.getByLabelText('Revoke plain@example.com'))
    await waitFor(() => expect(revokeSpy).toHaveBeenCalledWith('other-id'))
  })

  it('does not call revokeAdmin when confirm is declined', async () => {
    const revokeSpy = vi
      .spyOn(adminsApi, 'revokeAdmin')
      .mockResolvedValue({ ok: true })
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    const AdminUsersPage = await loadPage()
    render(withProviders(<AdminUsersPage />))

    await waitFor(() => screen.getByText('plain@example.com'))
    fireEvent.click(screen.getByLabelText('Revoke plain@example.com'))
    // Give the event loop a tick to show nothing happens.
    await new Promise((r) => setTimeout(r, 10))
    expect(revokeSpy).not.toHaveBeenCalled()
  })

  it('redirects plain admins away from the page (S-M4 role guard)', async () => {
    // Downgrade the mocked session to a plain admin.
    mockSession.current = {
      sub: 'plain-admin-id',
      email: 'plain@example.com',
      roles: ['admin'] as readonly string[],
      mfa_fresh: true,
      exp: 9_999_999_999,
    }
    const listSpy = vi.spyOn(adminsApi, 'listAdmins')

    const AdminUsersPage = await loadPage()
    const { container } = render(withProviders(<AdminUsersPage />))

    // Navigate renders nothing in this test's MemoryRouter — container is empty
    // of the page's heading, and the data fetch never fires.
    expect(container.textContent).not.toContain('Active admins')
    expect(container.textContent).not.toContain('Add Admin')
    expect(listSpy).not.toHaveBeenCalled()
  })
})
