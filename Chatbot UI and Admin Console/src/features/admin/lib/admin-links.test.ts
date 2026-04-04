import { describe, expect, it } from 'vitest'
import { buildTraceHref, clearTraceIdSearchParams, setTraceIdSearchParams } from './admin-links'

describe('admin trace links', () => {
  it('returns null for empty trace ids instead of emitting ?traceId=', () => {
    expect(buildTraceHref('')).toBeNull()
    expect(buildTraceHref('   ')).toBeNull()
    expect(buildTraceHref(undefined)).toBeNull()
  })

  it('removes traceId from cloned search params without mutating the original instance', () => {
    const current = new URLSearchParams('traceId=trace-123&search=hello')
    const next = clearTraceIdSearchParams(current)

    expect(current.get('traceId')).toBe('trace-123')
    expect(next.get('traceId')).toBeNull()
    expect(next.get('search')).toBe('hello')
  })

  it('writes a cloned traceId search param when a trace is selected', () => {
    const current = new URLSearchParams('search=hello')
    const next = setTraceIdSearchParams(current, 'trace-123')

    expect(current.get('traceId')).toBeNull()
    expect(next.get('traceId')).toBe('trace-123')
    expect(next.get('search')).toBe('hello')
  })
})
