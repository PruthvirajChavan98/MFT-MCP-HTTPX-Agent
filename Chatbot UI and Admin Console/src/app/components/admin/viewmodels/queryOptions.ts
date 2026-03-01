import { infiniteQueryOptions, queryOptions } from '@tanstack/react-query'
import type { FaqRecord } from '../../../../shared/types/admin'
import {
  fetchAdminTrace,
  fetchFaqCategories,
  fetchFaqs,
  fetchGuardrailEvents,
  fetchGuardrailJudgeSummary,
  fetchGuardrailQueueHealth,
  fetchGuardrailSummary,
  fetchGuardrailTrends,
  fetchSessionCostSummary,
  searchFaqSemantic,
  fetchTracesPage,
} from '../../../../shared/api/admin'

type GuardrailEventsParams = {
  adminKey: string
  tenantId: string
  decision: string
  offset: number
  limit: number
}

type TracesQueryParams = {
  adminKey: string
  search: string
  limit: number
}

type FaqSemanticParams = {
  adminKey: string
  query: string
  limit: number
  openrouterKey?: string
  groqKey?: string
}

export function sessionCostSummaryQueryOptions() {
  return queryOptions({
    queryKey: ['session-cost-summary'] as const,
    queryFn: fetchSessionCostSummary,
    refetchInterval: 30_000,
  })
}

export function tracesPageInfiniteQueryOptions(params: TracesQueryParams) {
  return infiniteQueryOptions({
    queryKey: ['traces-page', params.adminKey, params.search, params.limit] as const,
    queryFn: ({ pageParam }) =>
      fetchTracesPage(params.adminKey, {
        limit: params.limit,
        cursor: pageParam,
        search: params.search,
      }),
    enabled: Boolean(params.adminKey.trim()),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor || undefined,
  })
}

export function adminTraceQueryOptions(adminKey: string, traceId: string | null) {
  return queryOptions({
    queryKey: ['admin-trace', adminKey, traceId] as const,
    queryFn: () => fetchAdminTrace(adminKey, traceId || ''),
    enabled: Boolean(adminKey.trim() && traceId),
  })
}

export function guardrailSummaryQueryOptions(adminKey: string, tenantId: string) {
  return queryOptions({
    queryKey: ['guardrail-summary', adminKey, tenantId] as const,
    queryFn: () => fetchGuardrailSummary(adminKey, tenantId),
    enabled: Boolean(adminKey.trim() && tenantId.trim()),
    refetchInterval: 30_000,
  })
}

export function guardrailQueueHealthQueryOptions(adminKey: string) {
  return queryOptions({
    queryKey: ['guardrail-queue', adminKey] as const,
    queryFn: () => fetchGuardrailQueueHealth(adminKey),
    enabled: Boolean(adminKey.trim()),
    refetchInterval: 10_000,
  })
}

export function guardrailJudgeSummaryQueryOptions(adminKey: string) {
  return queryOptions({
    queryKey: ['guardrail-judge', adminKey] as const,
    queryFn: () => fetchGuardrailJudgeSummary(adminKey),
    enabled: Boolean(adminKey.trim()),
    refetchInterval: 30_000,
  })
}

export function guardrailTrendsQueryOptions(adminKey: string, tenantId: string, hours: number) {
  return queryOptions({
    queryKey: ['guardrail-trends', adminKey, tenantId, hours] as const,
    queryFn: () => fetchGuardrailTrends(adminKey, tenantId, hours),
    enabled: Boolean(adminKey.trim() && tenantId.trim()),
    refetchInterval: 30_000,
  })
}

export function guardrailEventsQueryOptions(params: GuardrailEventsParams) {
  return queryOptions({
    queryKey: [
      'guardrail-events',
      params.adminKey,
      params.tenantId,
      params.decision,
      params.offset,
      params.limit,
    ] as const,
    queryFn: () =>
      fetchGuardrailEvents(params.adminKey, {
        tenantId: params.tenantId,
        decision: params.decision,
        offset: params.offset,
        limit: params.limit,
      }),
    enabled: Boolean(params.adminKey.trim()),
  })
}

export function faqListQueryOptions(adminKey: string, limit = 500, skip = 0) {
  return queryOptions({
    queryKey: ['faqs', adminKey, limit, skip] as const,
    queryFn: () => fetchFaqs(adminKey, limit, skip),
    enabled: Boolean(adminKey.trim()),
    refetchInterval(query) {
      const data = query.state.data as FaqRecord[] | undefined
      const hasActive = data?.some(
        (f) => f.vector_status === 'pending' || f.vector_status === 'syncing',
      )
      return hasActive ? 5_000 : 30_000
    },
  })
}

export function faqCategoriesQueryOptions(adminKey: string) {
  return queryOptions({
    queryKey: ['faq-categories', adminKey] as const,
    queryFn: () => fetchFaqCategories(adminKey),
    enabled: Boolean(adminKey.trim()),
    staleTime: 60_000,
  })
}

export function faqSemanticSearchQueryOptions(params: FaqSemanticParams) {
  return queryOptions({
    queryKey: ['faq-semantic-search', params.adminKey, params.query, params.limit] as const,
    queryFn: () =>
      searchFaqSemantic(
        params.adminKey,
        params.query,
        params.limit,
        params.openrouterKey,
        params.groqKey,
      ),
    enabled: false,
  })
}
