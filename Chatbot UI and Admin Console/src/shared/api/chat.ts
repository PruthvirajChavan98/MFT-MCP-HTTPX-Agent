import { API_BASE_URL, requestJson } from './http'

export interface FeedbackPayload {
    session_id: string
    trace_id?: string
    rating: 'thumbs_up' | 'thumbs_down'
    comment?: string
    category?: string
}

export async function submitFeedback(payload: FeedbackPayload) {
    return requestJson<{ status: string; id: string; created_at: string }>({
        method: 'POST',
        path: '/agent/feedback',
        body: payload,
    })
}
