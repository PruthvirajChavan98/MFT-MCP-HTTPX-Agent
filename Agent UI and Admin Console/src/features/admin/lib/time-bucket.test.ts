import { describe, expect, it } from 'vitest'
import {
  bucketCount,
  bucketStartIso,
  formatBucketLabel,
  isGranularity,
  trailingBuckets,
} from './time-bucket'

describe('bucketStartIso', () => {
  it('returns YYYY-MM-DD for daily granularity in UTC', () => {
    // 2026-04-04 in UTC regardless of the host's timezone.
    expect(bucketStartIso('2026-04-04T15:30:00Z', 'day')).toBe('2026-04-04')
    expect(bucketStartIso('2026-04-04T00:00:00Z', 'day')).toBe('2026-04-04')
  })

  it('returns the Monday of the ISO week for weekly granularity', () => {
    // 2026-04-04 is a Saturday → week start is Monday 2026-03-30.
    expect(bucketStartIso('2026-04-04T12:00:00Z', 'week')).toBe('2026-03-30')
    // 2026-03-30 is Monday → bucket is itself.
    expect(bucketStartIso('2026-03-30T12:00:00Z', 'week')).toBe('2026-03-30')
    // 2026-04-05 is Sunday (still in the same ISO week as previous Monday).
    expect(bucketStartIso('2026-04-05T23:59:59Z', 'week')).toBe('2026-03-30')
  })

  it('handles ISO-week year rollover (Dec 31 can land in week 1 of next year)', () => {
    // 2019-12-31 is a Tuesday → Monday of its ISO week is 2019-12-30.
    expect(bucketStartIso('2019-12-31T12:00:00Z', 'week')).toBe('2019-12-30')
    // 2020-01-05 is a Sunday → still in the same ISO week starting 2019-12-30.
    expect(bucketStartIso('2020-01-05T12:00:00Z', 'week')).toBe('2019-12-30')
  })

  it('returns YYYY-MM-01 for monthly granularity', () => {
    expect(bucketStartIso('2026-04-04T12:00:00Z', 'month')).toBe('2026-04-01')
    expect(bucketStartIso('2026-04-30T23:59:59Z', 'month')).toBe('2026-04-01')
    expect(bucketStartIso('2026-01-01T00:00:00Z', 'month')).toBe('2026-01-01')
  })

  it('returns null for unparsable input', () => {
    expect(bucketStartIso('not-a-date', 'day')).toBeNull()
    expect(bucketStartIso('', 'week')).toBeNull()
  })
})

describe('formatBucketLabel', () => {
  it('formats daily buckets as "MMM D"', () => {
    expect(formatBucketLabel('2026-04-04', 'day')).toBe('Apr 4')
    expect(formatBucketLabel('2026-01-01', 'day')).toBe('Jan 1')
  })

  it('formats weekly buckets as "MMM D – MMM D" spanning 7 days inclusive', () => {
    // Week starting Monday 2026-03-30 runs through Sunday 2026-04-05.
    expect(formatBucketLabel('2026-03-30', 'week')).toBe('Mar 30 – Apr 5')
  })

  it('formats monthly buckets as "MMM YYYY"', () => {
    expect(formatBucketLabel('2026-04-01', 'month')).toBe('Apr 2026')
    expect(formatBucketLabel('2025-12-01', 'month')).toBe('Dec 2025')
  })
})

describe('bucketCount', () => {
  it('returns the trailing-window size per granularity', () => {
    expect(bucketCount('day')).toBe(30)
    expect(bucketCount('week')).toBe(12)
    expect(bucketCount('month')).toBe(12)
  })
})

describe('isGranularity', () => {
  it('accepts the three valid values', () => {
    expect(isGranularity('day')).toBe(true)
    expect(isGranularity('week')).toBe(true)
    expect(isGranularity('month')).toBe(true)
  })

  it('rejects anything else', () => {
    expect(isGranularity('hour')).toBe(false)
    expect(isGranularity('')).toBe(false)
    expect(isGranularity(null)).toBe(false)
    expect(isGranularity(undefined)).toBe(false)
    expect(isGranularity(42)).toBe(false)
  })
})

describe('trailingBuckets', () => {
  interface Row {
    when: string
  }

  function rows(...isoDates: string[]): Row[] {
    return isoDates.map((when) => ({ when }))
  }

  it('returns empty array when no items have parseable dates', () => {
    expect(
      trailingBuckets(
        rows('nope', 'also-nope'),
        (r) => r.when,
        () => 1,
        'day',
      ),
    ).toEqual([])
  })

  it('aggregates items into daily buckets and sorts ascending', () => {
    const result = trailingBuckets(
      rows(
        '2026-04-04T10:00:00Z',
        '2026-04-04T14:30:00Z',
        '2026-04-02T08:00:00Z',
      ),
      (r) => r.when,
      () => 1,
      'day',
    )
    const labels = result.map((p) => p.bucket)
    expect(labels).toEqual(['2026-04-02', '2026-04-03', '2026-04-04'])
    expect(result[0].value).toBe(1)
    expect(result[1].value).toBe(0) // gap-filled zero
    expect(result[2].value).toBe(2)
  })

  it('aggregates items into weekly buckets with ISO-week boundaries', () => {
    const result = trailingBuckets(
      rows(
        '2026-03-30T00:00:00Z', // Mon — week A
        '2026-04-05T23:00:00Z', // Sun — still week A
        '2026-04-06T00:00:00Z', // Mon — week B
      ),
      (r) => r.when,
      () => 1,
      'week',
    )
    expect(result.map((p) => p.bucket)).toEqual(['2026-03-30', '2026-04-06'])
    expect(result[0].value).toBe(2)
    expect(result[1].value).toBe(1)
  })

  it('aggregates items into monthly buckets with YYYY-MM-01 keys', () => {
    const result = trailingBuckets(
      rows(
        '2026-03-15T00:00:00Z',
        '2026-04-30T23:00:00Z',
        '2026-04-01T00:00:00Z',
      ),
      (r) => r.when,
      () => 1,
      'month',
    )
    expect(result.map((p) => p.bucket)).toEqual(['2026-03-01', '2026-04-01'])
    expect(result[0].value).toBe(1)
    expect(result[1].value).toBe(2)
  })

  it('uses the provided valueAccessor to sum arbitrary numeric fields', () => {
    interface CostRow {
      when: string
      amount: number
    }
    const rows: CostRow[] = [
      { when: '2026-04-04T01:00:00Z', amount: 0.05 },
      { when: '2026-04-04T23:00:00Z', amount: 0.07 },
      { when: '2026-04-05T00:00:00Z', amount: 0.1 },
    ]
    const result = trailingBuckets(
      rows,
      (r) => r.when,
      (r) => r.amount,
      'day',
    )
    expect(result[0].value).toBeCloseTo(0.12, 6)
    expect(result[1].value).toBeCloseTo(0.1, 6)
  })

  it('emits a human label beside each bucket key', () => {
    const result = trailingBuckets(
      rows('2026-04-04T10:00:00Z'),
      (r) => r.when,
      () => 1,
      'day',
    )
    expect(result[0].label).toBe('Apr 4')
  })

  it('drops items with missing dates without affecting totals', () => {
    const result = trailingBuckets(
      [
        { when: '2026-04-04T00:00:00Z' },
        { when: null as unknown as string },
        { when: undefined as unknown as string },
        { when: '2026-04-04T12:00:00Z' },
      ],
      (r) => r.when,
      () => 1,
      'day',
    )
    expect(result).toHaveLength(1)
    expect(result[0].value).toBe(2)
  })
})
