import { describe, expect, it, vi } from 'vitest'

const requestJsonMock = vi.fn()
const streamSseMock = vi.fn()

vi.mock('@shared/api/http', () => ({
  API_BASE_URL: '/api',
  requestJson: requestJsonMock,
}))

vi.mock('@shared/api/sse', () => ({
  streamSse: streamSseMock,
}))

describe('admin faq api contract', () => {
  it('fetchFaqs uses legacy stable endpoint', async () => {
    requestJsonMock.mockResolvedValueOnce({ items: [{ question: 'Q1', answer: 'A1' }] })
    const { fetchFaqs } = await import('./admin')

    const rows = await fetchFaqs(100, 0)

    expect(rows).toHaveLength(1)
    expect(requestJsonMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        path: '/agent/admin/faqs',
        query: { limit: 100, skip: 0 },
      }),
    )
  })

  it('ingestFaqBatch streams through stable batch-json endpoint', async () => {
    streamSseMock.mockImplementation(
      async (
        _url: string,
        _init: RequestInit,
        handlers: { onEvent: (eventName: string, data: string) => void },
      ) => {
        handlers.onEvent('message', 'Ingesting...')
        handlers.onEvent('done', 'complete')
      },
    )

    const { ingestFaqBatch } = await import('./admin')
    const progress: string[] = []

    await ingestFaqBatch([{ question: 'Q', answer: 'A' }], (msg) => progress.push(msg))

    expect(streamSseMock).toHaveBeenCalledWith(
      '/api/agent/admin/faqs/batch-json',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      }),
      expect.any(Object),
    )
    expect(progress).toContain('Ingesting...')
  })

  it('ingestFaqPdf posts multipart stream to upload-pdf endpoint', async () => {
    streamSseMock.mockImplementation(
      async (
        _url: string,
        _init: RequestInit,
        handlers: { onEvent: (eventName: string, data: string) => void },
      ) => {
        handlers.onEvent('message', 'Extracting...')
        handlers.onEvent('done', 'complete')
      },
    )

    const { ingestFaqPdf } = await import('./admin')
    const file = new File(['%PDF-1.4'], 'faqs.pdf', { type: 'application/pdf' })

    await ingestFaqPdf(file)

    const call = streamSseMock.mock.calls.find(([url]: [string]) =>
      url.endsWith('/agent/admin/faqs/upload-pdf'),
    )
    expect(call).toBeTruthy()
    const init = call?.[1] as RequestInit
    expect(init.method).toBe('POST')
    expect(init.credentials).toBe('include')
    expect(init.body).toBeInstanceOf(FormData)
    // FormData sets its own multipart Content-Type — do NOT pass `headers`
    expect(init.headers).toBeUndefined()
  })

  it('ingestFaqBatch surfaces structured SSE error payload message', async () => {
    streamSseMock.mockImplementation(
      async (
        _url: string,
        _init: RequestInit,
        handlers: {
          onEvent: (eventName: string, data: string, parsed?: unknown) => void
        },
      ) => {
        handlers.onEvent(
          'error',
          '{"message":"Batch FAQ ingest failed.","code":"faq_batch_ingest_failed","detail":"Batch size exceeds limit"}',
          {
            message: 'Batch FAQ ingest failed.',
            code: 'faq_batch_ingest_failed',
            detail: 'Batch size exceeds limit',
          },
        )
      },
    )

    const { ingestFaqBatch } = await import('./admin')

    await expect(ingestFaqBatch([{ question: 'Q', answer: 'A' }])).rejects.toThrow(
      'Batch FAQ ingest failed.',
    )
  })

  it('fetchFaqCategories uses additive managed endpoint', async () => {
    requestJsonMock.mockResolvedValueOnce({
      items: [{ id: 'billing', slug: 'billing', label: 'Billing', is_active: true }],
    })

    const { fetchFaqCategories } = await import('./admin')
    const rows = await fetchFaqCategories()

    expect(rows).toHaveLength(1)
    expect(requestJsonMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        path: '/agent/admin/faq-categories',
      }),
    )
  })

  it('deleteFaq supports id query for stable row identity', async () => {
    requestJsonMock.mockResolvedValueOnce({ status: 'success' })
    const { deleteFaq } = await import('./admin')

    await deleteFaq({ id: 'faq-123' })

    expect(requestJsonMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'DELETE',
        path: '/agent/admin/faqs',
        query: { id: 'faq-123' },
      }),
    )
  })

  it('searchFaqSemantic posts semantic query body to existing endpoint', async () => {
    requestJsonMock.mockResolvedValueOnce({
      status: 'success',
      results: [{ question: 'Q', answer: 'A', score: 0.9 }],
    })

    const { searchFaqSemantic } = await import('./admin')
    const rows = await searchFaqSemantic('loan', 5)

    expect(rows).toHaveLength(1)
    expect(requestJsonMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'POST',
        path: '/agent/admin/faqs/semantic-search',
        body: { query: 'loan', limit: 5 },
      }),
    )
  })
})
