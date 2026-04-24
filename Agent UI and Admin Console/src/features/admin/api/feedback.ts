import { requestJson } from '@shared/api/http'
import type { FeedbackRecord } from '../types/admin'

// ── API ──────────────────────────────────────────────────────────────────────
//
// Admin auth is JWT-cookie-based. `requestJson` sends `credentials: 'include'`
// on every call so the session cookie flows automatically. The public
// createFeedback endpoint is unauthenticated and unchanged.

export async function createFeedback(payload: {
  session_id: string
  trace_id?: string
  rating: 'thumbs_up' | 'thumbs_down'
  comment?: string
  category?: string
}): Promise<{ status: string; id: string }> {
  return requestJson({ method: 'POST', path: '/agent/feedback', body: payload })
}

export async function listFeedback(limit = 100): Promise<FeedbackRecord[]> {
  const response = await requestJson<{ items: FeedbackRecord[] }>({
    method: 'GET',
    path: '/agent/admin/feedback',
    query: { limit },
  })
  return response.items ?? []
}

export async function feedbackSummary(): Promise<{
  total: number
  thumbs_up: number
  thumbs_down: number
  positive_rate: number
}> {
  return requestJson({
    method: 'GET',
    path: '/agent/admin/feedback/summary',
  })
}
