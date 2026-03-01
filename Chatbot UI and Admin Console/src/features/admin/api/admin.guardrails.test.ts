import { describe, expect, it, vi } from 'vitest'

const requestJsonMock = vi.fn()
const withAdminHeadersMock = vi.fn((key?: string) => ({ 'X-Admin-Key': key ?? '' }))

vi.mock('@shared/api/http', () => ({
  API_BASE_URL: '/api',
  requestJson: requestJsonMock,
  withAdminHeaders: withAdminHeadersMock,
}))

describe('admin guardrails api contract', () => {
  it('sends tenant-aware query params for guardrail events', async () => {
    requestJsonMock.mockResolvedValueOnce({ items: [], count: 0, total: 0, offset: 0, limit: 25 })
    const { fetchGuardrailEvents } = await import('./admin')

    await fetchGuardrailEvents('admin-key', {
      tenantId: 'tenant-123',
      decision: 'deny',
      offset: 25,
      limit: 25,
    })

    expect(requestJsonMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        path: '/agent/admin/analytics/guardrails',
        query: expect.objectContaining({
          tenant_id: 'tenant-123',
          decision: 'deny',
          offset: 25,
          limit: 25,
        }),
      }),
    )
  })
})
