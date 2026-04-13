import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ADMIN_SESSION_EXPIRED_EVENT,
  API_BASE_URL,
  ApiError,
  requestJson,
} from './http'

/**
 * Build a minimal Response-like object that `fetch` mocks can return. We only
 * use `ok`, `status`, and `text()` inside `requestJson`, so we don't need a
 * full Response instance.
 */
function makeResponse(status: number, body: string): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => body,
  } as unknown as Response
}

function setCsrfCookie(value: string | null): void {
  Object.defineProperty(document, 'cookie', {
    writable: true,
    configurable: true,
    value: value === null ? '' : `mft_admin_csrf=${value}`,
  })
}

describe('requestJson', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch')
    setCsrfCookie(null)
  })

  afterEach(() => {
    fetchSpy.mockRestore()
    setCsrfCookie(null)
    vi.restoreAllMocks()
  })

  it('sends credentials=include on every request', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(200, '{"ok":true}'))
    await requestJson({ method: 'GET', path: '/foo' })
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    const init = fetchSpy.mock.calls[0][1] as RequestInit
    expect(init.credentials).toBe('include')
  })

  it('does NOT inject X-CSRF-Token on GET even when cookie present', async () => {
    setCsrfCookie('the-csrf-token')
    fetchSpy.mockResolvedValueOnce(makeResponse(200, '{}'))
    await requestJson({ method: 'GET', path: '/foo' })
    const init = fetchSpy.mock.calls[0][1] as RequestInit
    const headers = (init.headers ?? {}) as Record<string, string>
    expect(headers['X-CSRF-Token']).toBeUndefined()
  })

  it('injects X-CSRF-Token on POST when cookie present', async () => {
    setCsrfCookie('csrf-value-123')
    fetchSpy.mockResolvedValueOnce(makeResponse(200, '{}'))
    await requestJson({ method: 'POST', path: '/foo', body: { x: 1 } })
    const init = fetchSpy.mock.calls[0][1] as RequestInit
    const headers = (init.headers ?? {}) as Record<string, string>
    expect(headers['X-CSRF-Token']).toBe('csrf-value-123')
  })

  it('omits X-CSRF-Token on POST when no cookie present', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(200, '{}'))
    await requestJson({ method: 'POST', path: '/foo', body: { x: 1 } })
    const init = fetchSpy.mock.calls[0][1] as RequestInit
    const headers = (init.headers ?? {}) as Record<string, string>
    expect(headers['X-CSRF-Token']).toBeUndefined()
  })

  it('injects X-CSRF-Token on PUT and DELETE', async () => {
    setCsrfCookie('csrf-xyz')
    fetchSpy.mockResolvedValue(makeResponse(200, '{}'))

    await requestJson({ method: 'PUT', path: '/a', body: { x: 1 } })
    await requestJson({ method: 'DELETE', path: '/a' })

    const putHeaders = (fetchSpy.mock.calls[0][1] as RequestInit).headers as Record<string, string>
    const delHeaders = (fetchSpy.mock.calls[1][1] as RequestInit).headers as Record<string, string>
    expect(putHeaders['X-CSRF-Token']).toBe('csrf-xyz')
    expect(delHeaders['X-CSRF-Token']).toBe('csrf-xyz')
  })

  it('returns parsed JSON body on 200', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(200, '{"value":42}'))
    const result = await requestJson<{ value: number }>({ method: 'GET', path: '/x' })
    expect(result).toEqual({ value: 42 })
  })

  it('throws ApiError with resolved message on 500', async () => {
    fetchSpy.mockResolvedValueOnce(
      makeResponse(500, '{"detail":"server blew up"}'),
    )
    await expect(requestJson({ method: 'GET', path: '/x' })).rejects.toMatchObject({
      name: 'ApiError',
      status: 500,
      message: 'server blew up',
    })
  })

  it('throws ApiError that is instanceof ApiError on failure', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(400, '{"detail":"bad"}'))
    let thrown: unknown = null
    try {
      await requestJson({ method: 'GET', path: '/x' })
    } catch (err) {
      thrown = err
    }
    expect(thrown).toBeInstanceOf(ApiError)
  })

  it('dispatches admin:session-expired event on 401 for non-auth paths', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(401, '{"detail":"nope"}'))
    const listener = vi.fn()
    window.addEventListener(ADMIN_SESSION_EXPIRED_EVENT, listener)
    try {
      await expect(
        requestJson({ method: 'GET', path: '/agent/admin/faqs' }),
      ).rejects.toBeInstanceOf(ApiError)
      expect(listener).toHaveBeenCalledTimes(1)
    } finally {
      window.removeEventListener(ADMIN_SESSION_EXPIRED_EVENT, listener)
    }
  })

  it('does NOT dispatch session-expired event on 401 for /admin/auth/* paths', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(401, '{"detail":"nope"}'))
    const listener = vi.fn()
    window.addEventListener(ADMIN_SESSION_EXPIRED_EVENT, listener)
    try {
      await expect(
        requestJson({ method: 'POST', path: '/admin/auth/login', body: {} }),
      ).rejects.toBeInstanceOf(ApiError)
      expect(listener).not.toHaveBeenCalled()
    } finally {
      window.removeEventListener(ADMIN_SESSION_EXPIRED_EVENT, listener)
    }
  })

  it('builds the URL using API_BASE_URL + path', async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(200, '{}'))
    await requestJson({ method: 'GET', path: '/foo/bar' })
    const url = fetchSpy.mock.calls[0][0]
    expect(url).toBe(`${API_BASE_URL}/foo/bar`)
  })
})
