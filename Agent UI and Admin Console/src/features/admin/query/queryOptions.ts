import { infiniteQueryOptions, queryOptions } from '@tanstack/react-query'
import type { FaqRecord } from '@features/admin/types/admin'
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
} from '@features/admin/api/admin'

/** Standard polling interval for admin dashboard queries. */
export const ADMIN_REFETCH_MS = 30_000

type GuardrailEventsParams = {
  tenantId: string
  decision: string
  offset: number
  limit: number
}

type TracesQueryParams = {
  search: string
  limit: number
  /**
   * Optional canonical category slug. Bypassed when empty.
   * Deep-link from /admin/categories → /admin/traces?category=<slug>.
   */
  category?: string
}

type FaqSemanticParams = {
  query: string
  limit: number
}

export function sessionCostSummaryQueryOptions() {
  return queryOptions({
    queryKey: ['session-cost-summary'] as const,
    queryFn: fetchSessionCostSummary,
    refetchInterval: ADMIN_REFETCH_MS,
  })
}

export function tracesPageInfiniteQueryOptions(params: TracesQueryParams) {
  return infiniteQueryOptions({
    queryKey: ['traces-page', params.search, params.category ?? '', params.limit] as const,
    queryFn: ({ pageParam }) =>
      fetchTracesPage({
        limit: params.limit,
        cursor: pageParam,
        search: params.search,
        category: params.category,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor || undefined,
  })
}

export function adminTraceQueryOptions(traceId: string | null) {
  return queryOptions({
    queryKey: ['admin-trace', traceId] as const,
    queryFn: () => fetchAdminTrace(traceId || ''),
    enabled: Boolean(traceId),
  })
}

export function guardrailSummaryQueryOptions(tenantId: string) {
  return queryOptions({
    queryKey: ['guardrail-summary', tenantId] as const,
    queryFn: () => fetchGuardrailSummary(tenantId),
    enabled: Boolean(tenantId.trim()),
    refetchInterval: ADMIN_REFETCH_MS,
  })
}

export function guardrailQueueHealthQueryOptions() {
  return queryOptions({
    queryKey: ['guardrail-queue'] as const,
    queryFn: () => fetchGuardrailQueueHealth(),
    refetchInterval: 10_000,
  })
}

export function guardrailJudgeSummaryQueryOptions() {
  return queryOptions({
    queryKey: ['guardrail-judge'] as const,
    queryFn: () => fetchGuardrailJudgeSummary(),
    refetchInterval: ADMIN_REFETCH_MS,
  })
}

export function guardrailTrendsQueryOptions(tenantId: string, hours: number) {
  return queryOptions({
    queryKey: ['guardrail-trends', tenantId, hours] as const,
    queryFn: () => fetchGuardrailTrends(tenantId, hours),
    enabled: Boolean(tenantId.trim()),
    refetchInterval: ADMIN_REFETCH_MS,
  })
}

export function guardrailEventsQueryOptions(params: GuardrailEventsParams) {
  return queryOptions({
    queryKey: [
      'guardrail-events',
      params.tenantId,
      params.decision,
      params.offset,
      params.limit,
    ] as const,
    queryFn: () =>
      fetchGuardrailEvents({
        tenantId: params.tenantId,
        decision: params.decision,
        offset: params.offset,
        limit: params.limit,
      }),
  })
}

export function faqListQueryOptions(limit = 500, skip = 0) {
  return queryOptions({
    queryKey: ['faqs', limit, skip] as const,
    queryFn: () => fetchFaqs(limit, skip),
    refetchInterval(query) {
      const data = query.state.data as FaqRecord[] | undefined
      const hasActive = data?.some(
        (f) => f.vector_status === 'pending' || f.vector_status === 'syncing',
      )
      return hasActive ? 5_000 : ADMIN_REFETCH_MS
    },
  })
}

export function faqCategoriesQueryOptions() {
  return queryOptions({
    queryKey: ['faq-categories'] as const,
    queryFn: () => fetchFaqCategories(),
    staleTime: 60_000,
  })
}

export function faqSemanticSearchQueryOptions(params: FaqSemanticParams) {
  return queryOptions({
    queryKey: ['faq-semantic-search', params.query, params.limit] as const,
    queryFn: () => searchFaqSemantic(params.query, params.limit),
    enabled: false,
  })
}

export function adminsQueryOptions() {
  return queryOptions({
    queryKey: ['admins'] as const,
    queryFn: async () => {
      const { listAdmins } = await import('@features/admin/api/admins')
      return listAdmins()
    },
    staleTime: 30_000,
  })
}
