import { api } from '../lib/api';
import type {
  EvalSearchResponse,
  EvalTraceResponse,
  FulltextResponse,
  VectorSearchRequest,
  VectorSearchResponse,
  MetricSummaryResponse,
  MetricFailuresResponse,
  SessionSearchResponse,
  QuestionTypesResponse
} from '../types/eval';

const ROOT = '/eval';

export const EvalService = {
  search(params: Record<string, any>) {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
    });
    return api.get<EvalSearchResponse>(`${ROOT}/search?${q.toString()}`);
  },

  sessions(params: { limit?: number; offset?: number; app_id?: string }) {
    const q = new URLSearchParams();
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    if (params.app_id) q.set('app_id', params.app_id);
    return api.get<SessionSearchResponse>(`${ROOT}/sessions?${q.toString()}`);
  },

  trace(traceId: string) {
    return api.get<EvalTraceResponse>(`${ROOT}/trace/${encodeURIComponent(traceId)}`);
  },

  fulltext(params: Record<string, any>) {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) q.set(k, String(v));
    });
    return api.get<FulltextResponse>(`${ROOT}/fulltext?${q.toString()}`);
  },

  vectorSearch(req: VectorSearchRequest, openRouterKey?: string) {
    const headers: Record<string, string> = {};
    if (openRouterKey?.trim()) headers['X-OpenRouter-Key'] = openRouterKey.trim();
    return api.post<VectorSearchResponse>(`${ROOT}/vector-search`, req, headers);
  },

  metricsSummary() {
    return api.get<MetricSummaryResponse>(`${ROOT}/metrics/summary`);
  },

  metricsFailures(params: Record<string, any>) {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
    });
    return api.get<MetricFailuresResponse>(`${ROOT}/metrics/failures?${q.toString()}`);
  },

  questionTypes(params: { limit?: number }) {
    return api.get<QuestionTypesResponse>(`${ROOT}/question-types?limit=${params.limit || 200}`);
  },
};
