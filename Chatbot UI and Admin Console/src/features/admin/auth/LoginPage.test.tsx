import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const loginMock = vi.fn()
const navigateMock = vi.fn()

let errorState: string | null = null
let isLoadingState = false

vi.mock('./AdminAuthProvider', () => ({
  useAdminAuth: () => ({
    session: null,
    isLoading: isLoadingState,
    error: errorState,
    login: loginMock,
    logout: vi.fn(),
    verifyMfa: vi.fn(),
    refreshSession: vi.fn(),
  }),
}))

vi.mock('react-router', () => ({
  useNavigate: () => navigateMock,
}))

import { LoginPage } from './LoginPage'

describe('LoginPage', () => {
  beforeEach(() => {
    loginMock.mockReset()
    navigateMock.mockReset()
    errorState = null
    isLoadingState = false
  })

  afterEach(() => {
    cleanup()
  })

  it('renders email and password inputs with correct autocomplete hints', () => {
    render(<LoginPage />)
    const email = screen.getByLabelText(/email/i) as HTMLInputElement
    const password = screen.getByLabelText(/password/i) as HTMLInputElement
    expect(email.type).toBe('email')
    expect(email.autocomplete).toBe('email')
    expect(password.type).toBe('password')
    expect(password.autocomplete).toBe('current-password')
  })

  it('disables the submit button when either field is empty', () => {
    render(<LoginPage />)
    const submit = screen.getByRole('button', { name: /sign in/i }) as HTMLButtonElement
    expect(submit.disabled).toBe(true)

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.c' } })
    expect(submit.disabled).toBe(true)

    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'pw' } })
    expect(submit.disabled).toBe(false)
  })

  it('calls login() with form values and navigates to /admin on success', async () => {
    loginMock.mockResolvedValueOnce({ mfa_required: true })
    render(<LoginPage />)

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'admin@example.com' },
    })
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'horse-battery-staple' },
    })
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!)

    await vi.waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith('admin@example.com', 'horse-battery-staple')
      expect(navigateMock).toHaveBeenCalledWith('/admin', { replace: true })
    })
  })

  it('shows local error from thrown exception when login fails', async () => {
    loginMock.mockRejectedValueOnce(new Error('invalid credentials'))
    render(<LoginPage />)

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.c' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'pw' } })
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!)

    await vi.waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/invalid credentials/i)
    })
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('shows provider-level error when local error is absent', () => {
    errorState = 'session hydration failed'
    render(<LoginPage />)
    expect(screen.getByRole('alert')).toHaveTextContent(/session hydration failed/i)
  })

  it('displays "Signing in…" while submission is in flight', async () => {
    let resolveLogin: (v: { mfa_required: boolean }) => void = () => {}
    loginMock.mockImplementationOnce(
      () => new Promise<{ mfa_required: boolean }>((resolve) => {
        resolveLogin = resolve
      }),
    )
    render(<LoginPage />)

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.c' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'pw' } })
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!)

    await vi.waitFor(() => {
      expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled()
    })

    // Release the pending promise so the component can settle
    resolveLogin({ mfa_required: true })
  })
})
