import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Vitest hoists vi.mock() to the top of the file, so any symbols the factory
// references must be declared via vi.hoisted() which runs in the hoisted slot.
const { requestJsonMock, TestApiError } = vi.hoisted(() => {
  class TestApiError extends Error {
    status: number
    detail: unknown
    constructor(message: string, status: number, detail: unknown) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.detail = detail
    }
  }
  return {
    requestJsonMock: vi.fn(),
    TestApiError,
  }
})

vi.mock('@/shared/api/http', () => ({
  requestJson: requestJsonMock,
  ApiError: TestApiError,
  ADMIN_SESSION_EXPIRED_EVENT: 'admin:session-expired',
  API_BASE_URL: '/api',
  RUNTIME_CONFIG: {},
}))

// Stub react-router Navigate so AuthGuard redirect is observable in tests
vi.mock('react-router', () => ({
  Navigate: ({ to }: { to: string }) => (
    <div data-testid="navigate" data-to={to} />
  ),
}))

import { AdminAuthProvider, useAdminAuth } from './AdminAuthProvider'
import { AuthGuard } from '../layout/AdminLayout'

const SESSION_SAMPLE = {
  sub: 'super_admin',
  roles: ['admin', 'super_admin'],
  mfa_fresh: false,
  exp: 9999999999,
}

function TestConsumer() {
  const { session, isLoading, error, login, logout, verifyMfa } = useAdminAuth()
  // Wrap login / verifyMfa in try/catch — they re-throw after setting error
  // state, which is the correct production pattern but would leak an
  // unhandled rejection in test click handlers.
  const safeLogin = async () => {
    try {
      await login('a@b.c', 'pw')
    } catch {
      /* error state is observed via the provider */
    }
  }
  const safeVerifyMfa = async () => {
    try {
      await verifyMfa('123456')
    } catch {
      /* error state is observed via the provider */
    }
  }
  return (
    <div>
      <span data-testid="session">{session ? session.sub : 'none'}</span>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="error">{error ?? 'none'}</span>
      <button onClick={() => void safeLogin()}>login</button>
      <button onClick={() => void logout()}>logout</button>
      <button onClick={() => void safeVerifyMfa()}>mfa</button>
    </div>
  )
}

async function waitForLoadingDone(): Promise<void> {
  await vi.waitFor(() => {
    expect(screen.getByTestId('loading').textContent).toBe('false')
  })
}

describe('AdminAuthProvider', () => {
  beforeEach(() => {
    requestJsonMock.mockReset()
  })

  afterEach(() => {
    cleanup()
  })

  it('hydrates session from GET /admin/auth/me on mount', async () => {
    requestJsonMock.mockResolvedValueOnce(SESSION_SAMPLE)
    render(
      <AdminAuthProvider>
        <TestConsumer />
      </AdminAuthProvider>,
    )
    await waitForLoadingDone()
    expect(screen.getByTestId('session').textContent).toBe('super_admin')
    expect(screen.getByTestId('error').textContent).toBe('none')
    expect(requestJsonMock).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', path: '/admin/auth/me' }),
    )
  })

  it('treats 401 from /me as no session, silently (no error state)', async () => {
    requestJsonMock.mockRejectedValueOnce(new TestApiError('unauthenticated', 401, null))
    render(
      <AdminAuthProvider>
        <TestConsumer />
      </AdminAuthProvider>,
    )
    await waitForLoadingDone()
    expect(screen.getByTestId('session').textContent).toBe('none')
    expect(screen.getByTestId('error').textContent).toBe('none')
  })

  it('surfaces non-401 /me errors as error state', async () => {
    requestJsonMock.mockRejectedValueOnce(new TestApiError('server down', 500, null))
    render(
      <AdminAuthProvider>
        <TestConsumer />
      </AdminAuthProvider>,
    )
    await waitForLoadingDone()
    expect(screen.getByTestId('session').textContent).toBe('none')
    expect(screen.getByTestId('error').textContent).toBe('server down')
  })

  it('login() POSTs to /admin/auth/login then refreshes session via /me', async () => {
    // mount: /me returns 401 (no session)
    requestJsonMock.mockRejectedValueOnce(new TestApiError('unauth', 401, null))
    // login call: POST succeeds
    requestJsonMock.mockResolvedValueOnce({ ok: true, mfa_required: true })
    // follow-up /me call
    requestJsonMock.mockResolvedValueOnce(SESSION_SAMPLE)

    render(
      <AdminAuthProvider>
        <TestConsumer />
      </AdminAuthProvider>,
    )
    await waitForLoadingDone()

    screen.getByRole('button', { name: 'login' }).click()

    await vi.waitFor(() => {
      expect(screen.getByTestId('session').textContent).toBe('super_admin')
    })

    const loginCall = requestJsonMock.mock.calls.find(
      (call) => (call[0] as { path: string }).path === '/admin/auth/login',
    )
    expect(loginCall).toBeDefined()
    expect((loginCall?.[0] as { body: unknown }).body).toEqual({
      email: 'a@b.c',
      password: 'pw',
    })
  })

  it('login() failure sets error and does not set session', async () => {
    requestJsonMock.mockRejectedValueOnce(new TestApiError('unauth', 401, null)) // /me
    requestJsonMock.mockRejectedValueOnce(new TestApiError('bad creds', 401, null)) // /login

    render(
      <AdminAuthProvider>
        <TestConsumer />
      </AdminAuthProvider>,
    )
    await waitForLoadingDone()

    screen.getByRole('button', { name: 'login' }).click()

    await vi.waitFor(() => {
      expect(screen.getByTestId('error').textContent).toBe('bad creds')
    })
    expect(screen.getByTestId('session').textContent).toBe('none')
  })

  it('logout() POSTs /admin/auth/logout and clears session', async () => {
    requestJsonMock.mockResolvedValueOnce(SESSION_SAMPLE) // mount
    requestJsonMock.mockResolvedValueOnce({ ok: true }) // logout

    render(
      <AdminAuthProvider>
        <TestConsumer />
      </AdminAuthProvider>,
    )
    await waitForLoadingDone()
    expect(screen.getByTestId('session').textContent).toBe('super_admin')

    screen.getByRole('button', { name: 'logout' }).click()

    await vi.waitFor(() => {
      expect(screen.getByTestId('session').textContent).toBe('none')
    })
    const logoutCall = requestJsonMock.mock.calls.find(
      (call) => (call[0] as { path: string }).path === '/admin/auth/logout',
    )
    expect(logoutCall).toBeDefined()
  })

  it('logout() clears session even if the server call rejects', async () => {
    requestJsonMock.mockResolvedValueOnce(SESSION_SAMPLE) // mount
    requestJsonMock.mockRejectedValueOnce(new TestApiError('server down', 500, null))

    render(
      <AdminAuthProvider>
        <TestConsumer />
      </AdminAuthProvider>,
    )
    await waitForLoadingDone()

    screen.getByRole('button', { name: 'logout' }).click()

    await vi.waitFor(() => {
      expect(screen.getByTestId('session').textContent).toBe('none')
    })
  })

  it('verifyMfa() POSTs and refreshes session', async () => {
    requestJsonMock.mockResolvedValueOnce(SESSION_SAMPLE) // mount
    requestJsonMock.mockResolvedValueOnce({ ok: true }) // mfa/verify
    requestJsonMock.mockResolvedValueOnce({
      ...SESSION_SAMPLE,
      mfa_fresh: true,
    }) // /me follow-up

    render(
      <AdminAuthProvider>
        <TestConsumer />
      </AdminAuthProvider>,
    )
    await waitForLoadingDone()

    screen.getByRole('button', { name: 'mfa' }).click()

    await vi.waitFor(() => {
      const mfaCall = requestJsonMock.mock.calls.find(
        (call) => (call[0] as { path: string }).path === '/admin/auth/mfa/verify',
      )
      expect(mfaCall).toBeDefined()
    })
  })

  it('useAdminAuth() throws when used outside the provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      expect(() => render(<TestConsumer />)).toThrow(
        /useAdminAuth must be used inside/,
      )
    } finally {
      spy.mockRestore()
    }
  })
})

// ─────────────── AuthGuard (co-located — same provider tree) ───────────────

function GuardedChild() {
  return <div data-testid="guarded">secret admin content</div>
}

describe('AuthGuard (inside AdminAuthProvider)', () => {
  beforeEach(() => {
    requestJsonMock.mockReset()
  })

  afterEach(() => {
    cleanup()
  })

  it('renders null while session is hydrating (isLoading=true)', async () => {
    // Never-resolving /me keeps the provider in loading state
    let resolve: (v: unknown) => void = () => {}
    requestJsonMock.mockReturnValueOnce(
      new Promise((r) => {
        resolve = r
      }),
    )

    render(
      <AdminAuthProvider>
        <AuthGuard>
          <GuardedChild />
        </AuthGuard>
      </AdminAuthProvider>,
    )

    // Guard renders nothing while loading — no guarded content, no navigate
    expect(screen.queryByTestId('guarded')).toBeNull()
    expect(screen.queryByTestId('navigate')).toBeNull()

    // Clean up the pending promise
    resolve(null)
  })

  it('redirects to /admin/login when no session is present', async () => {
    requestJsonMock.mockRejectedValueOnce(new TestApiError('no session', 401, null))

    render(
      <AdminAuthProvider>
        <AuthGuard>
          <GuardedChild />
        </AuthGuard>
      </AdminAuthProvider>,
    )

    await vi.waitFor(() => {
      const nav = screen.getByTestId('navigate')
      expect(nav.getAttribute('data-to')).toBe('/admin/login')
    })
    expect(screen.queryByTestId('guarded')).toBeNull()
  })

  it('passes through when a JWT session is present', async () => {
    requestJsonMock.mockResolvedValueOnce(SESSION_SAMPLE)

    render(
      <AdminAuthProvider>
        <AuthGuard>
          <GuardedChild />
        </AuthGuard>
      </AdminAuthProvider>,
    )

    await vi.waitFor(() => {
      expect(screen.getByTestId('guarded')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('navigate')).toBeNull()
  })
})
