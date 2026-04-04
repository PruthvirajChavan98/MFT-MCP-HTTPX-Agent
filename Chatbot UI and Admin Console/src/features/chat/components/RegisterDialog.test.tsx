import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { motionReactMock } from '@/test/mocks/motion'
import { RegisterDialog } from './RegisterDialog'

const { requestOtpMock, verifyOtpMock, toastSuccessMock, toastErrorMock } = vi.hoisted(() => ({
  requestOtpMock: vi.fn(),
  verifyOtpMock: vi.fn(),
  toastSuccessMock: vi.fn(),
  toastErrorMock: vi.fn(),
}))

vi.mock('motion/react', motionReactMock)

vi.mock('@shared/api/crm', () => ({
  requestOtp: requestOtpMock,
  verifyOtp: verifyOtpMock,
}))

vi.mock('sonner', () => ({
  toast: {
    success: toastSuccessMock,
    error: toastErrorMock,
  },
}))

function renderDialog() {
  return render(<RegisterDialog open onOpenChange={vi.fn()} />)
}

async function fillRegistrationForm() {
  fireEvent.change(screen.getByLabelText(/mobile number/i), {
    target: { value: '9876543210' },
  })
  fireEvent.change(screen.getByLabelText(/first name/i), {
    target: { value: 'Test' },
  })
  fireEvent.change(screen.getByLabelText(/last name/i), {
    target: { value: 'User' },
  })
}

const REQUEST_RESULT = {
  otpSent: true,
  token: null,
  user: null,
  loansCreated: 0,
  expiresAt: null,
  message: 'OTP sent',
}

const VERIFY_RESULT = {
  otpSent: false,
  token: 'demo-token',
  user: {
    id: 'user_1',
    phone: '9876543210',
    firstname: 'Test',
    lastname: 'User',
    dob: null,
  },
  loansCreated: 1,
  expiresAt: '2026-05-01T00:00:00.000Z',
  message: 'Registered',
}

beforeEach(() => {
  requestOtpMock.mockReset()
  verifyOtpMock.mockReset()
  toastSuccessMock.mockReset()
  toastErrorMock.mockReset()
  vi.stubGlobal(
    'ResizeObserver',
    class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
  requestOtpMock.mockResolvedValue(REQUEST_RESULT)
  verifyOtpMock.mockResolvedValue(VERIFY_RESULT)
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('RegisterDialog', () => {
  it('uses 7d as the default keepMeFor value', async () => {
    renderDialog()

    await fillRegistrationForm()
    fireEvent.click(screen.getByRole('button', { name: /send otp via whatsapp/i }))

    await waitFor(() => {
      expect(requestOtpMock).toHaveBeenCalledWith(
        expect.objectContaining({
          keepMeFor: '7d',
        }),
      )
    })
  }, 10000)

  it('sends the selected keepMeFor value when requesting an OTP', async () => {
    renderDialog()

    await fillRegistrationForm()
    fireEvent.click(screen.getByLabelText(/30 days/i))
    fireEvent.click(screen.getByRole('button', { name: /send otp via whatsapp/i }))

    await waitFor(() => {
      expect(requestOtpMock).toHaveBeenCalledWith(
        expect.objectContaining({
          keepMeFor: '30d',
        }),
      )
    })
  }, 10000)

  it('preserves keepMeFor through verification and resend', async () => {
    vi.useFakeTimers()
    renderDialog()

    await fillRegistrationForm()
    fireEvent.click(screen.getByLabelText(/90 days/i))
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /send otp via whatsapp/i }))
      await Promise.resolve()
    })

    const otpInput = document.querySelector('input[data-input-otp]')
    expect(otpInput).not.toBeNull()

    for (let tick = 0; tick < 61; tick += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000)
      })
    }

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /^Resend OTP$/i }))
      await Promise.resolve()
    })

    expect(requestOtpMock).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        keepMeFor: '90d',
      }),
    )

    fireEvent.change(otpInput as HTMLInputElement, { target: { value: '123456' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /verify otp/i }))
      await Promise.resolve()
    })

    expect(verifyOtpMock).toHaveBeenCalledWith(
      expect.objectContaining({
        keepMeFor: '90d',
        otp: '123456',
      }),
    )
  }, 20000)
})
