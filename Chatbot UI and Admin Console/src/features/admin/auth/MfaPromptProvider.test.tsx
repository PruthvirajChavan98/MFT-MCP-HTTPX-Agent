import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest'

// ─────────── hoisted mocks ───────────
//
// Vitest hoists vi.mock() to the top of the file, so any symbols the factory
// references must be declared via vi.hoisted() which runs in the hoisted slot.
// See tasks/lessons.md L6 — we've been burned by this before.
const { verifyMfaMock, TestApiError } = vi.hoisted(() => {
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
    verifyMfaMock: vi.fn<(code: string) => Promise<void>>(),
    TestApiError,
  }
})

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

vi.mock('@/shared/api/http', () => ({
  ApiError: TestApiError,
  ADMIN_SESSION_EXPIRED_EVENT: 'admin:session-expired',
  ADMIN_MFA_REQUIRED_EVENT: 'admin:mfa-required',
}))

import {
  ADMIN_MFA_REQUIRED_EVENT,
  MfaCancelled,
  MfaPromptProvider,
} from './MfaPromptProvider'
import { useMfaPrompt } from './useMfaPrompt'

// ─────────── consumer harness ───────────

interface HarnessProps {
  /** Capture promptMfa resolutions for assertion. */
  onResolve?: () => void
  onReject?: (err: unknown) => void
  /** Op to run through withMfa; default throws a 403 mfa_required ApiError once. */
  op?: () => Promise<string>
  /** The label passed to withMfa — surfaced in the modal heading. */
  label?: string
}

function Harness({
  onResolve,
  onReject,
  op,
  label = 'save changes',
}: HarnessProps) {
  const { promptMfa, withMfa } = useMfaPrompt()

  const runPrompt = async () => {
    try {
      await promptMfa(label)
      onResolve?.()
    } catch (err) {
      onReject?.(err)
    }
  }

  const runWithMfa = async () => {
    if (!op) return
    try {
      const result = await withMfa(label, op)
      onResolve?.()
      ;(globalThis as unknown as { __withMfaResult?: string }).__withMfaResult = result
    } catch (err) {
      onReject?.(err)
    }
  }

  return (
    <div>
      <button onClick={() => void runPrompt()}>run-prompt</button>
      <button onClick={() => void runWithMfa()}>run-with-mfa</button>
    </div>
  )
}

function renderWithProvider(props: HarnessProps = {}) {
  return render(
    <MfaPromptProvider>
      <Harness {...props} />
    </MfaPromptProvider>,
  )
}

async function clickVerifyWithCode(code: string): Promise<void> {
  const input = screen.getByLabelText(/authenticator code/i) as HTMLInputElement
  fireEvent.change(input, { target: { value: code } })
  const verifyBtn = screen.getByRole('button', { name: /^verify$/i })
  fireEvent.click(verifyBtn)
}

async function clickCancel(): Promise<void> {
  const cancelBtn = screen.getByRole('button', { name: /^cancel$/i })
  fireEvent.click(cancelBtn)
}

function makeMfaRequiredError(): InstanceType<typeof TestApiError> {
  return new TestApiError('mfa required', 403, {
    code: 'mfa_required',
    operation: 'test',
    message: 'MFA required',
  })
}

// ─────────── tests ───────────

describe('MfaPromptProvider / useMfaPrompt', () => {
  beforeEach(() => {
    verifyMfaMock.mockReset()
    delete (globalThis as { __withMfaResult?: string }).__withMfaResult
  })

  afterEach(() => {
    cleanup()
  })

  it('promptMfa resolves after successful verifyMfa', async () => {
    const onResolve = vi.fn<() => void>()
    verifyMfaMock.mockResolvedValueOnce(undefined)
    renderWithProvider({ onResolve })

    fireEvent.click(screen.getByRole('button', { name: 'run-prompt' }))

    // Modal should be visible
    await screen.findByLabelText(/authenticator code/i)
    await clickVerifyWithCode('123456')

    await waitFor(() => {
      expect(verifyMfaMock).toHaveBeenCalledWith('123456')
      expect(onResolve).toHaveBeenCalledOnce()
    })
    // Modal should have closed
    expect(screen.queryByLabelText(/authenticator code/i)).toBeNull()
  })

  it('promptMfa rejects with MfaCancelled when user clicks Cancel', async () => {
    const onReject = vi.fn<(err: unknown) => void>()
    renderWithProvider({ onReject })

    fireEvent.click(screen.getByRole('button', { name: 'run-prompt' }))
    await screen.findByLabelText(/authenticator code/i)
    await clickCancel()

    await waitFor(() => {
      expect(onReject).toHaveBeenCalledOnce()
    })
    const err = onReject.mock.calls[0][0]
    expect(err).toBeInstanceOf(MfaCancelled)
  })

  it('opens modal when window fires admin:mfa-required', async () => {
    renderWithProvider()
    expect(screen.queryByLabelText(/authenticator code/i)).toBeNull()

    act(() => {
      window.dispatchEvent(new CustomEvent(ADMIN_MFA_REQUIRED_EVENT))
    })

    // The MfaChallenge's description paragraph carries the actionLabel; the
    // ambient listener passes 'continue', so we should see "... to continue."
    const input = await screen.findByLabelText(/authenticator code/i)
    expect(input).toBeTruthy()
    expect(
      screen.getByText(/Enter your authenticator code to continue\./i),
    ).toBeTruthy()
  })

  it('withMfa retries the wrapped fn once after successful TOTP', async () => {
    const fn = vi
      .fn<() => Promise<string>>()
      .mockRejectedValueOnce(makeMfaRequiredError())
      .mockResolvedValueOnce('ok')
    verifyMfaMock.mockResolvedValueOnce(undefined)
    const onResolve = vi.fn<() => void>()
    renderWithProvider({ op: fn, onResolve })

    fireEvent.click(screen.getByRole('button', { name: 'run-with-mfa' }))

    await screen.findByLabelText(/authenticator code/i)
    await clickVerifyWithCode('123456')

    await waitFor(() => {
      expect(fn).toHaveBeenCalledTimes(2) // once failed, once retried
      expect(onResolve).toHaveBeenCalledOnce()
    })
    expect((globalThis as { __withMfaResult?: string }).__withMfaResult).toBe('ok')
  })

  it('withMfa rejects with MfaCancelled when user cancels and does NOT retry', async () => {
    const fn = vi
      .fn<() => Promise<string>>()
      .mockRejectedValueOnce(makeMfaRequiredError())
    const onReject = vi.fn<(err: unknown) => void>()
    renderWithProvider({ op: fn, onReject })

    fireEvent.click(screen.getByRole('button', { name: 'run-with-mfa' }))
    await screen.findByLabelText(/authenticator code/i)
    await clickCancel()

    await waitFor(() => {
      expect(onReject).toHaveBeenCalledOnce()
    })
    expect(fn).toHaveBeenCalledTimes(1) // no retry
    expect(onReject.mock.calls[0][0]).toBeInstanceOf(MfaCancelled)
  })

  it('withMfa propagates non-403 errors without opening the modal', async () => {
    const serverError = new TestApiError('boom', 500, null)
    const fn = vi.fn<() => Promise<string>>().mockRejectedValueOnce(serverError)
    const onReject = vi.fn<(err: unknown) => void>()
    renderWithProvider({ op: fn, onReject })

    fireEvent.click(screen.getByRole('button', { name: 'run-with-mfa' }))

    await waitFor(() => {
      expect(onReject).toHaveBeenCalledOnce()
    })
    expect(onReject.mock.calls[0][0]).toBe(serverError)
    expect(screen.queryByLabelText(/authenticator code/i)).toBeNull()
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('withMfa propagates 403 errors whose detail.code !== mfa_required', async () => {
    const forbiddenError = new TestApiError('forbidden', 403, { code: 'not_admin' })
    const fn = vi.fn<() => Promise<string>>().mockRejectedValueOnce(forbiddenError)
    const onReject = vi.fn<(err: unknown) => void>()
    renderWithProvider({ op: fn, onReject })

    fireEvent.click(screen.getByRole('button', { name: 'run-with-mfa' }))

    await waitFor(() => {
      expect(onReject).toHaveBeenCalledOnce()
    })
    expect(onReject.mock.calls[0][0]).toBe(forbiddenError)
    expect(screen.queryByLabelText(/authenticator code/i)).toBeNull()
  })

  it('useMfaPrompt throws when used outside MfaPromptProvider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      expect(() =>
        render(<Harness />),
      ).toThrow(/useMfaPrompt must be used inside/)
    } finally {
      spy.mockRestore()
    }
  })
})
