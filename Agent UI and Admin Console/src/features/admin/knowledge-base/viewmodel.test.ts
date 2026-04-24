import { describe, expect, it } from 'vitest'
import { buildKnowledgeBaseViewModel, normalizeFaqRecord } from './viewmodel'

describe('knowledge base viewmodel', () => {
  it('normalizes additive faq fields with stable fallback id', () => {
    const row = normalizeFaqRecord({
      question: 'What is the refund policy?',
      answer: '30-day refund.',
      vectorized: true,
    })

    expect(row.id).toContain('faq:')
    expect(row.vectorStatus).toBe('synced')
    expect(row.vectorized).toBe(true)
    expect(row.category).toBe('Technical')
  })

  it('builds deterministic stats and category options', () => {
    const model = buildKnowledgeBaseViewModel({
      faqs: [
        {
          id: 'faq-1',
          question: 'Refund',
          answer: 'Billing answer',
          category: 'Billing',
          tags: ['refund'],
          vector_status: 'synced',
          created_at: '2026-01-01',
        },
        {
          id: 'faq-2',
          question: 'Password reset',
          answer: 'Account answer',
          category: 'Account',
          tags: ['security'],
          vector_status: 'pending',
          created_at: '2026-01-02',
        },
      ],
      categories: [
        { id: 'billing', slug: 'billing', label: 'Billing', is_active: true },
        { id: 'account', slug: 'account', label: 'Account', is_active: true },
      ],
      selectedCategory: 'All',
      sortField: 'createdAt',
      sortDir: 'desc',
    })

    expect(model.stats.total).toBe(2)
    expect(model.stats.vectorized).toBe(1)
    expect(model.stats.pending).toBe(1)
    expect(model.stats.categories).toBe(2)
    expect(model.categoryOptions[0]).toMatchObject({ label: 'All', count: 2 })
  })

  it('filters by category and sorts by question', () => {
    const model = buildKnowledgeBaseViewModel({
      faqs: [
        {
          id: 'faq-a',
          question: 'Export data',
          answer: 'Use CSV.',
          category: 'Data',
          tags: ['export', 'csv'],
          vector_status: 'synced',
          created_at: '2026-01-02',
        },
        {
          id: 'faq-b',
          question: 'Reset password',
          answer: 'Use forgot password.',
          category: 'Account',
          tags: ['security'],
          vector_status: 'synced',
          created_at: '2026-01-01',
        },
      ],
      categories: [],
      selectedCategory: 'Data',
      sortField: 'question',
      sortDir: 'asc',
    })

    expect(model.rows).toHaveLength(1)
    expect(model.rows[0].id).toBe('faq-a')
  })
})
