import { API_BASE_URL, requestJson } from '@shared/api/http'
import { streamSse } from '@shared/api/sse'
import type { FaqCategory, FaqRecord } from '../types/admin'

// ── Knowledge Base (FAQ) ──────────────────────────────────────────────────────
//
// Admin auth is JWT-cookie-based (ADMIN_AUTH_ENABLED=true). `requestJson`
// already sends `credentials: 'include'` so the cookie flows automatically;
// SSE calls add `credentials: 'include'` inline because `streamSse` is a
// thinner wrapper over `fetch` that doesn't apply defaults.

export async function fetchFaqs(limit = 200, skip = 0): Promise<FaqRecord[]> {
  const response = await requestJson<{ items: FaqRecord[] }>({
    method: 'GET',
    path: '/agent/admin/faqs',
    query: { limit, skip },
  })
  return response.items ?? []
}

export async function updateFaq(payload: {
  id?: string
  original_question?: string
  new_question?: string
  new_answer?: string
  new_category?: string
  new_tags?: string[]
}): Promise<{ status: string; message?: string }> {
  return requestJson({
    method: 'PUT',
    path: '/agent/admin/faqs',
    body: payload,
  })
}

export async function deleteFaq(
  target: string | { id?: string; question?: string },
): Promise<{ status: string; message?: string }> {
  const query =
    typeof target === 'string'
      ? { question: target }
      : {
          ...(target.id ? { id: target.id } : {}),
          ...(target.question ? { question: target.question } : {}),
        }
  return requestJson({
    method: 'DELETE',
    path: '/agent/admin/faqs',
    query,
  })
}

export async function clearAllFaqs(): Promise<{ status: string; message?: string }> {
  return requestJson({
    method: 'DELETE',
    path: '/agent/admin/faqs/all',
  })
}

export async function fetchFaqCategories(): Promise<FaqCategory[]> {
  const response = await requestJson<{ items: FaqCategory[] }>({
    method: 'GET',
    path: '/agent/admin/faq-categories',
  })
  return response.items ?? []
}

export async function searchFaqSemantic(
  query: string,
  limit = 5,
): Promise<Array<{ question: string; answer: string; score: number }>> {
  const response = await requestJson<{
    status: string
    results: Array<{ question: string; answer: string; score: number }>
  }>({
    method: 'POST',
    path: '/agent/admin/faqs/semantic-search',
    body: { query, limit },
  })
  return response.results ?? []
}

function resolveSseErrorMessage(data: string, parsed?: unknown): string {
  if (parsed && typeof parsed === 'object') {
    const payload = parsed as {
      message?: string
      detail?: string | { message?: string; detail?: string }
    }
    if (typeof payload.message === 'string' && payload.message.trim()) return payload.message.trim()
    if (typeof payload.detail === 'string' && payload.detail.trim()) return payload.detail.trim()
    if (payload.detail && typeof payload.detail === 'object') {
      if (
        typeof payload.detail.message === 'string' &&
        payload.detail.message.trim()
      ) {
        return payload.detail.message.trim()
      }
      if (
        typeof payload.detail.detail === 'string' &&
        payload.detail.detail.trim()
      ) {
        return payload.detail.detail.trim()
      }
    }
  }
  if (data.trim()) return data
  return 'FAQ ingest failed'
}

export async function ingestFaqBatch(
  items: Array<{ question: string; answer: string; category?: string; tags?: string[] }>,
  onProgress?: (message: string) => void,
): Promise<string> {
  let lastMessage = 'Ingest complete'
  await streamSse(
    `${API_BASE_URL}/agent/admin/faqs/batch-json`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
    },
    {
      onEvent: (eventName, data, parsed) => {
        if (eventName === 'error') throw new Error(resolveSseErrorMessage(data, parsed))
        if (data) {
          lastMessage = data
          onProgress?.(data)
        }
      },
    },
  )
  return lastMessage
}

export async function ingestFaqPdf(
  file: File,
  onProgress?: (message: string) => void,
): Promise<string> {
  let lastMessage = 'PDF ingest complete'
  const formData = new FormData()
  formData.append('file', file)

  await streamSse(
    `${API_BASE_URL}/agent/admin/faqs/upload-pdf`,
    {
      method: 'POST',
      credentials: 'include',
      body: formData,
    },
    {
      onEvent: (eventName, data, parsed) => {
        if (eventName === 'error') throw new Error(resolveSseErrorMessage(data, parsed))
        if (data) {
          lastMessage = data
          onProgress?.(data)
        }
      },
    },
  )

  return lastMessage
}
