import type { FaqCategory, FaqRecord, FaqVectorStatus } from '@features/admin/types/admin'

export type KnowledgeBaseSortField = 'question' | 'category' | 'createdAt'
export type KnowledgeBaseSortDir = 'asc' | 'desc'

export type KnowledgeBaseFaqRow = {
  id: string
  serverId?: string
  question: string
  answer: string
  category: string
  tags: string[]
  createdAt: string
  updatedAt?: string
  vectorStatus: FaqVectorStatus
  vectorError: string | null
  vectorized: boolean
}

export type KnowledgeBaseCategoryOption = {
  id: string
  label: string
  count: number
}

export type KnowledgeBaseStats = {
  total: number
  vectorized: number
  syncing: number
  pending: number
  failed: number
  categories: number
}

export type KnowledgeBaseViewModel = {
  rows: KnowledgeBaseFaqRow[]
  categoryOptions: KnowledgeBaseCategoryOption[]
  stats: KnowledgeBaseStats
}

function normalizeString(value: string | undefined | null): string {
  return (value || '').trim()
}

function normalizeTags(tags: string[] | undefined): string[] {
  if (!tags?.length) return []
  const seen = new Set<string>()
  const normalized: string[] = []
  for (const tag of tags) {
    const value = normalizeString(tag).toLowerCase()
    if (!value || seen.has(value)) continue
    seen.add(value)
    normalized.push(value)
  }
  return normalized
}

function normalizeVectorStatus(record: FaqRecord): FaqVectorStatus {
  if (record.vector_status) return record.vector_status
  return record.vectorized ? 'synced' : 'pending'
}

export function normalizeFaqRecord(record: FaqRecord): KnowledgeBaseFaqRow {
  const vectorStatus = normalizeVectorStatus(record)
  const normalizedQuestion = normalizeString(record.question)
  const fallbackId = `faq:${normalizedQuestion.toLowerCase()}`

  return {
    id: normalizeString(record.id) || fallbackId,
    serverId: normalizeString(record.id) || undefined,
    question: normalizedQuestion,
    answer: normalizeString(record.answer),
    category: normalizeString(record.category) || 'Technical',
    tags: normalizeTags(record.tags),
    createdAt: normalizeString(record.created_at),
    updatedAt: normalizeString(record.updated_at) || undefined,
    vectorStatus,
    vectorError: record.vector_error ?? null,
    vectorized: vectorStatus === 'synced',
  }
}

function sortRows(
  rows: KnowledgeBaseFaqRow[],
  field: KnowledgeBaseSortField,
  dir: KnowledgeBaseSortDir,
): KnowledgeBaseFaqRow[] {
  const sorted = [...rows].sort((a, b) => {
    let comp = 0
    if (field === 'createdAt') {
      const av = a.createdAt || a.updatedAt || ''
      const bv = b.createdAt || b.updatedAt || ''
      comp = av.localeCompare(bv)
    } else if (field === 'category') {
      comp = a.category.localeCompare(b.category)
    } else {
      comp = a.question.localeCompare(b.question)
    }
    return dir === 'asc' ? comp : -comp
  })

  return sorted
}

function filterRows(
  rows: KnowledgeBaseFaqRow[],
  selectedCategory: string,
): KnowledgeBaseFaqRow[] {
  return rows.filter((row) => selectedCategory === 'All' || row.category === selectedCategory)
}

function buildCategoryOptions(
  rows: KnowledgeBaseFaqRow[],
  categories: FaqCategory[],
): KnowledgeBaseCategoryOption[] {
  const counts = new Map<string, number>()
  for (const row of rows) {
    counts.set(row.category, (counts.get(row.category) ?? 0) + 1)
  }

  const ordered = categories
    .map((category) => category.label)
    .filter((label, index, labels) => labels.indexOf(label) === index)

  for (const row of rows) {
    if (!ordered.includes(row.category)) ordered.push(row.category)
  }

  const categoryOptions: KnowledgeBaseCategoryOption[] = ordered.map((label) => ({
    id: label.toLowerCase(),
    label,
    count: counts.get(label) ?? 0,
  }))

  return [{ id: 'all', label: 'All', count: rows.length }, ...categoryOptions]
}

export function buildKnowledgeBaseViewModel(params: {
  faqs: FaqRecord[]
  categories: FaqCategory[]
  selectedCategory: string
  sortField: KnowledgeBaseSortField
  sortDir: KnowledgeBaseSortDir
}): KnowledgeBaseViewModel {
  const normalizedRows = params.faqs.map(normalizeFaqRecord)
  const filteredRows = filterRows(normalizedRows, params.selectedCategory)
  const rows = sortRows(filteredRows, params.sortField, params.sortDir)

  const vectorized = normalizedRows.filter((row) => row.vectorStatus === 'synced').length
  const syncing = normalizedRows.filter((row) => row.vectorStatus === 'syncing').length
  const failed = normalizedRows.filter((row) => row.vectorStatus === 'failed').length
  const pending = normalizedRows.filter((row) => row.vectorStatus === 'pending').length
  const stats: KnowledgeBaseStats = {
    total: normalizedRows.length,
    vectorized,
    syncing,
    pending,
    failed,
    categories: new Set(normalizedRows.map((row) => row.category)).size,
  }

  return {
    rows,
    categoryOptions: buildCategoryOptions(normalizedRows, params.categories),
    stats,
  }
}
