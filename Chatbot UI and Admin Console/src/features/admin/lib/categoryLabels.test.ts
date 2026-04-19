import { describe, expect, it } from 'vitest'
import { CATEGORY_SLUG_OTHER, formatCategoryLabel, isOtherCategory } from './categoryLabels'

describe('formatCategoryLabel', () => {
  it('maps canonical slugs to friendly labels', () => {
    expect(formatCategoryLabel('loan_products_and_eligibility')).toBe('Loan products & eligibility')
    expect(formatCategoryLabel('fraud_and_security')).toBe('Fraud & security')
    expect(formatCategoryLabel(CATEGORY_SLUG_OTHER)).toBe('Uncategorized')
  })

  it('falls back to title-case replacement for unknown slugs', () => {
    expect(formatCategoryLabel('new_unmapped_slug')).toBe('New Unmapped Slug')
  })

  it('treats null/undefined/empty as uncategorized', () => {
    expect(formatCategoryLabel(null)).toBe('Uncategorized')
    expect(formatCategoryLabel(undefined)).toBe('Uncategorized')
    expect(formatCategoryLabel('')).toBe('Uncategorized')
  })
})

describe('isOtherCategory', () => {
  it('matches the canonical slug', () => {
    expect(isOtherCategory('other')).toBe(true)
  })

  it('matches legacy "Unknown" rows too so coverage metrics stay correct', () => {
    expect(isOtherCategory('Unknown')).toBe(true)
    expect(isOtherCategory('unknown')).toBe(true)
  })

  it('returns false for classified slugs', () => {
    expect(isOtherCategory('fraud_and_security')).toBe(false)
    expect(isOtherCategory('loan_products_and_eligibility')).toBe(false)
  })

  it('treats null/undefined as other (no data → no coverage)', () => {
    expect(isOtherCategory(null)).toBe(true)
    expect(isOtherCategory(undefined)).toBe(true)
  })
})
