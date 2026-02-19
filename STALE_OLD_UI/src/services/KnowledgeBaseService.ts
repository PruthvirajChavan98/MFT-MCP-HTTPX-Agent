import { api } from '../lib/api';
import { SSESubscription } from '../lib/sse';
import { sessionState } from '../stores/sessionStore';

const ROOT = '/admin/faqs';

export interface FAQItem {
  question: string;
  answer: string;
}

export interface IngestCallback {
  onProgress: (percent: number, message: string) => void;
  onDone: (result: any) => void;
  onError: (error: string) => void;
}

function getHeaders(adminKey?: string) {
  const headers: Record<string, string> = {};
  if (sessionState.keys.openrouter) {
    headers['X-OpenRouter-Key'] = sessionState.keys.openrouter;
  }
  if (adminKey) headers['X-Admin-Key'] = adminKey;
  return headers;
}

export const KnowledgeBaseService = {
  // --- Streaming Uploads (PDF) ---
  async uploadPdfStream(file: File, adminKey: string | undefined, cb: IngestCallback) {
    const formData = new FormData();
    formData.append('file', file);

    // We append keys to URL query params for the streaming connection
    // to ensure they pass through without complex header logic in SSESubscription for now.
    const query = new URLSearchParams();
    if (adminKey) query.set('x_admin_key', adminKey);
    // Note: If backend strictly requires Headers for SSE, we need to update SSESubscription.
    // Assuming api.ts pattern, we will stick to raw fetch here for the specific
    // multipart/form-data case to guarantee headers are set correctly.

    try {
      const headers = getHeaders(adminKey);
      // Let browser set content-type for FormData
      const res = await fetch(`/agent${ROOT}/upload-pdf`, {
        method: 'POST',
        headers: headers,
        body: formData,
      });

      if (!res.ok) throw new Error(await res.text());
      if (!res.body) throw new Error('No stream');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          if (!part.trim()) continue;
          // Manual SSE Parsing for this specific endpoint
          const lines = part.split('\n');
          let event = '', data = '';
          for (const line of lines) {
            if (line.startsWith('event:')) event = line.slice(6).trim();
            else if (line.startsWith('data:')) data = line.slice(5).trim();
          }
          if (event === 'progress') {
            try {
              const p = JSON.parse(data);
              cb.onProgress(p.percent, p.message);
            } catch {}
          } else if (event === 'done') {
            try { cb.onDone(JSON.parse(data)); } catch {}
          } else if (event === 'error') {
            cb.onError(data);
          }
        }
      }
    } catch (e: any) {
      cb.onError(e.message);
    }
  },

  // --- Streaming Ingest (JSON) ---
  async ingestJsonStream(items: FAQItem[], adminKey: string | undefined, cb: IngestCallback) {
    const payload = { items };
    const headers = { ...getHeaders(adminKey), 'Content-Type': 'application/json' };

    try {
      const res = await fetch(`/agent${ROOT}/batch-json`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(await res.text());
      if (!res.body) throw new Error('No stream');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          if (!part.trim()) continue;
          const lines = part.split('\n');
          let event = '', data = '';
          for (const line of lines) {
            if (line.startsWith('event:')) event = line.slice(6).trim();
            else if (line.startsWith('data:')) data = line.slice(5).trim();
          }
          if (event === 'progress') {
             try {
               const p = JSON.parse(data);
               cb.onProgress(p.percent, p.message);
             } catch {}
          } else if (event === 'done') {
             try { cb.onDone(JSON.parse(data)); } catch {}
          } else if (event === 'error') {
             cb.onError(data);
          }
        }
      }
    } catch (e: any) {
      cb.onError(e.message);
    }
  },

  // --- Standard CRUD ---
  async getFaqs(limit = 100, skip = 0) {
    return api.get<any>(`${ROOT}?limit=${limit}&skip=${skip}`);
  },

  async deleteFaq(question: string, adminKey?: string) {
    const headers = getHeaders(adminKey);
    const params = new URLSearchParams({ question });
    return api.delete(`${ROOT}?${params.toString()}`, headers);
  },

  async editFaq(original_question: string, new_question: string, new_answer: string, adminKey?: string) {
    const headers = getHeaders(adminKey);
    return api.put(ROOT, { original_question, new_question, new_answer }, headers);
  },

  async clearAll(adminKey?: string) {
    const headers = getHeaders(adminKey);
    return api.delete(`${ROOT}/all`, headers);
  },

  async semanticSearch(query: string, adminKey?: string) {
    const headers = getHeaders(adminKey);
    return api.post(`${ROOT}/semantic-search`, { query, limit: 10 }, headers);
  },

  async semanticDelete(query: string, adminKey?: string) {
    const headers = getHeaders(adminKey);
    return api.post(`${ROOT}/semantic-delete`, { query, threshold: 0.90 }, headers);
  }
};
