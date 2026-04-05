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

export function blankEntry(category = DEFAULT_CATEGORY): FaqEntryDraft {
  return {
    question: '',
    answer: '',
    category,
    tags: '',
    errors: {},
  }
}
