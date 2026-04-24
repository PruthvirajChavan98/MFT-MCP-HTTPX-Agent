import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const verifyMfaMock = vi.fn()

vi.mock('./AdminAuthProvider', () => ({
  useAdminAuth: () => ({
    session: null,
    isLoading: false,
    error: null,
    login: vi.fn(),
    logout: vi.fn(),
    verifyMfa: verifyMfaMock,
    refreshSession: vi.fn(),
  }),
}))

import { MfaChallenge } from './MfaChallenge'

describe('MfaChallenge', () => {
  let onVerified: ReturnType<typeof vi.fn<() => void>>
  let onCancel: ReturnType<typeof vi.fn<() => void>>

  beforeEach(() => {
    onVerified = vi.fn<() => void>()
    onCancel = vi.fn<() => void>()
    verifyMfaMock.mockReset()
  })

  afterEach(() => {
    cleanup()
  })

  it('renders the code input with numeric inputMode and one-time-code autocomplete', () => {
    render(<MfaChallenge onVerified={onVerified} onCancel={onCancel} />)
    const input = screen.getByLabelText(/authenticator code/i) as HTMLInputElement
    expect(input.inputMode).toBe('numeric')
    expect(input.autocomplete).toBe('one-time-code')
    expect(input.maxLength).toBe(6)
  })

  it('strips non-digit characters and caps input at 6 characters', () => {
    render(<MfaChallenge onVerified={onVerified} onCancel={onCancel} />)
    const input = screen.getByLabelText(/authenticator code/i) as HTMLInputElement
    fireEvent.change(input, { target: { value: 'a1b2c3d4e5f6g7' } })
    expect(input.value).toBe('123456')
  })

  it('disables the verify button until 6 digits are entered', () => {
    render(<MfaChallenge onVerified={onVerified} onCancel={onCancel} />)
    const verify = screen.getByRole('button', { name: /verify/i }) as HTMLButtonElement
    expect(verify.disabled).toBe(true)

    const input = screen.getByLabelText(/authenticator code/i)
    fireEvent.change(input, { target: { value: '12345' } })
    expect(verify.disabled).toBe(true)

    fireEvent.change(input, { target: { value: '123456' } })
    expect(verify.disabled).toBe(false)
  })

  it('calls verifyMfa with the code and onVerified on success', async () => {
    verifyMfaMock.mockResolvedValueOnce(undefined)
    render(<MfaChallenge onVerified={onVerified} onCancel={onCancel} />)

    fireEvent.change(screen.getByLabelText(/authenticator code/i), {
      target: { value: '987654' },
    })
    fireEvent.submit(screen.getByRole('button', { name: /verify/i }).closest('form')!)

    await vi.waitFor(() => {
      expect(verifyMfaMock).toHaveBeenCalledWith('987654')
      expect(onVerified).toHaveBeenCalledTimes(1)
    })
  })

  it('shows an error and does NOT call onVerified on verifyMfa failure', async () => {
    verifyMfaMock.mockRejectedValueOnce(new Error('invalid TOTP code'))
    render(<MfaChallenge onVerified={onVerified} onCancel={onCancel} />)

    fireEvent.change(screen.getByLabelText(/authenticator code/i), {
      target: { value: '000000' },
    })
    fireEvent.submit(screen.getByRole('button', { name: /verify/i }).closest('form')!)

    await vi.waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/invalid totp code/i)
    })
    expect(onVerified).not.toHaveBeenCalled()
  })

  it('cancel button invokes onCancel', () => {
    render(<MfaChallenge onVerified={onVerified} onCancel={onCancel} />)
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('renders actionLabel in the prompt text (lowercased)', () => {
    render(
      <MfaChallenge
        onVerified={onVerified}
        onCancel={onCancel}
        actionLabel="Save FAQ"
      />,
    )
    // Regex targets the specific phrase the component composes with the label
    expect(
      screen.getByText(/enter your authenticator code to save faq\./i),
    ).toBeInTheDocument()
  })

  it('falls back to the generic prompt when actionLabel is omitted', () => {
    render(<MfaChallenge onVerified={onVerified} onCancel={onCancel} />)
    expect(
      screen.getByText(/enter the 6-digit code from your authenticator app\./i),
    ).toBeInTheDocument()
  })
})
