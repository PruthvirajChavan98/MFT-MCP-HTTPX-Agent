import '@testing-library/jest-dom/vitest'
import { afterAll, beforeAll, vi } from 'vitest'

const DEPRECATION_PATTERN = /deprecat(?:ed|ion)|\[dep\d+\]/i

function toText(value: unknown): string {
  if (typeof value === 'string') return value
  if (value instanceof Error) return value.message

  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function assertNoDeprecation(args: unknown[]): void {
  const message = args.map(toText).join(' ')
  if (DEPRECATION_PATTERN.test(message)) {
    throw new Error(`Deprecation warning detected during tests: ${message}`)
  }
}

let warnSpy: ReturnType<typeof vi.spyOn> | null = null
let errorSpy: ReturnType<typeof vi.spyOn> | null = null

beforeAll(() => {
  const originalWarn = console.warn
  const originalError = console.error

  warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args: unknown[]) => {
    assertNoDeprecation(args)
    originalWarn(...args)
  })

  errorSpy = vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
    assertNoDeprecation(args)
    originalError(...args)
  })
})

afterAll(() => {
  warnSpy?.mockRestore()
  errorSpy?.mockRestore()
})
