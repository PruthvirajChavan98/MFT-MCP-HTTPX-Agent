import { requestJson, withAdminHeaders } from '@shared/api/http'
import type { FeedbackRecord } from '../types/admin'

// ── API ──────────────────────────────────────────────────────────────────────

export async function createFeedback(payload: {
  session_id: string
  trace_id?: string
  rating: 'thumbs_up' | 'thumbs_down'
  comment?: string
  category?: string
}): Promise<{ status: string; id: string }> {
  return requestJson({ method: 'POST', path: '/agent/feedback', body: payload })
}

export async function listFeedback(
  adminKey: string,
  limit = 100,
): Promise<FeedbackRecord[]> {
  const response = await requestJson<{ items: FeedbackRecord[] }>({
    method: 'GET',
    path: '/agent/admin/feedback',
    query: { limit },
    headers: withAdminHeaders(adminKey),
  })
  return response.items ?? []
}

export async function feedbackSummary(adminKey: string): Promise<{
  total: number
  thumbs_up: number
  thumbs_down: number
  positive_rate: number
}> {
  return requestJson({
    method: 'GET',
    path: '/agent/admin/feedback/summary',
    headers: withAdminHeaders(adminKey),
  })
}
