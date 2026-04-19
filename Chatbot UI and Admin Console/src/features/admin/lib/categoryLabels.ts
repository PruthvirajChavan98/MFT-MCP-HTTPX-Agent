/**
 * Display labels for question-category slugs.
 *
 * Backend emits canonical lowercase slugs (see
 * backend/src/agent_service/api/admin_analytics/category_map.py). The URL
 * keeps the slug verbatim so the trace filter predicate matches. For display,
 * humanize via this map — unknown slugs fall back to title-cased words.
 */

const CANONICAL_CATEGORY_LABELS: Record<string, string> = {
  loan_products_and_eligibility: 'Loan products & eligibility',
  application_status_and_approval: 'Application status & approval',
  theft_claim_and_non_seizure: 'Theft claim & non-seizure',
  disbursal_and_bank_credit: 'Disbursal & bank credit',
  profile_kyc_and_access: 'Profile, KYC & access',
  credit_report_and_bureau: 'Credit report & bureau',
  foreclosure_and_closure: 'Foreclosure & closure',
  emi_payments_and_charges: 'EMI, payments & charges',
  collections_and_recovery: 'Collections & recovery',
  fraud_and_security: 'Fraud & security',
  customer_support_channels: 'Customer support channels',
  other: 'Uncategorized',
}

export const CATEGORY_SLUG_OTHER = 'other'

export function formatCategoryLabel(slug: string | null | undefined): string {
  if (!slug) return CANONICAL_CATEGORY_LABELS[CATEGORY_SLUG_OTHER]
  const mapped = CANONICAL_CATEGORY_LABELS[slug]
  if (mapped) return mapped
  return slug.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function isOtherCategory(slug: string | null | undefined): boolean {
  // Historic rows may have emitted 'Unknown' before the slug fix landed —
  // treat both as the same bucket when computing coverage.
  if (!slug) return true
  const lowered = slug.toLowerCase()
  return lowered === CATEGORY_SLUG_OTHER || lowered === 'unknown'
}
