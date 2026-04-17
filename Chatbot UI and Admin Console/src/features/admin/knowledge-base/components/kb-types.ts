export type SemanticMatch = {
  question: string
  answer: string
  score: number
}

export type EntryErrors = {
  q?: string
  a?: string
}

export type FaqEntryDraft = {
  uid: string
  question: string
  answer: string
  category: string
  tags: string
  errors: EntryErrors
}

export const DEFAULT_CATEGORY = 'Technical'

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) return error.message
  if (typeof error === 'string' && error.trim()) return error
  return 'Request failed'
}

function newUid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `faq-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export function blankEntry(category = DEFAULT_CATEGORY): FaqEntryDraft {
  return {
    uid: newUid(),
    question: '',
    answer: '',
    category,
    tags: '',
    errors: {},
  }
}

export function entryFromExisting(
  initial: { question: string; answer: string; category: string; tags: string[] },
  stableId?: string,
): FaqEntryDraft {
  return {
    uid: stableId ?? newUid(),
    question: initial.question,
    answer: initial.answer,
    category: initial.category,
    tags: initial.tags.join(', '),
    errors: {},
  }
}
