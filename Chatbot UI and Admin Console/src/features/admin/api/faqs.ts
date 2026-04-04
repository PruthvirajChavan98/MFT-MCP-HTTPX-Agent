import { API_BASE_URL, requestJson, withAdminHeaders } from '@shared/api/http'
import { streamSse } from '@shared/api/sse'
import type { FaqCategory, FaqRecord } from '../types/admin'

// ── Knowledge Base (FAQ) ──────────────────────────────────────────────────────

export async function fetchFaqs(
  adminKey: string,
  limit = 200,
  skip = 0,
): Promise<FaqRecord[]> {
  const response = await requestJson<{ items: FaqRecord[] }>({
    method: 'GET',
    path: '/agent/admin/faqs',
    query: { limit, skip },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function updateFaq(
  adminKey: string,
  payload: {
    id?: string
    original_question?: string
    new_question?: string
    new_answer?: string
    new_category?: string
    new_tags?: string[]
  },
): Promise<{ status: string; message?: string }> {
  return requestJson({
    method: 'PUT',
    path: '/agent/admin/faqs',
    headers: withAdminHeaders(adminKey),
    body: payload,
  })
}

export async function deleteFaq(
  adminKey: string,
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
    headers: withAdminHeaders(adminKey),
  })
}

export async function clearAllFaqs(
  adminKey: string,
): Promise<{ status: string; message?: string }> {
  return requestJson({
    method: 'DELETE',
    path: '/agent/admin/faqs/all',
    headers: withAdminHeaders(adminKey),
  })
}

export async function fetchFaqCategories(adminKey: string): Promise<FaqCategory[]> {
  const response = await requestJson<{ items: FaqCategory[] }>({
    method: 'GET',
    path: '/agent/admin/faq-categories',
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function searchFaqSemantic(
  adminKey: string,
  query: string,
  limit = 5,
): Promise<Array<{ question: string; answer: string; score: number }>> {
  const response = await requestJson<{ status: string; results: Array<{ question: string; answer: string; score: number }> }>({
    method: 'POST',
    path: '/agent/admin/faqs/semantic-search',
    headers: withAdminHeaders(adminKey),
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
  adminKey: string,
  items: Array<{ question: string; answer: string; category?: string; tags?: string[] }>,
  onProgress?: (message: string) => void,
): Promise<string> {
  let lastMessage = 'Ingest complete'
  await streamSse(
    `${API_BASE_URL}/agent/admin/faqs/batch-json`,
    {
      method: 'POST',
      headers: withAdminHeaders(adminKey, {
        'Content-Type': 'application/json',
      }),
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
  adminKey: string,
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
      headers: withAdminHeaders(adminKey),
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
