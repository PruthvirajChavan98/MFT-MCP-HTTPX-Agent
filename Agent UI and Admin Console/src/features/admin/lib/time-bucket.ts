/**
 * Client-side time-series bucketing helpers for admin dashboard charts.
 *
 * Charts receive raw rows (traces, session rows) from the existing API and
 * re-bucket them into daily / weekly / monthly groups here, so we don't
 * need backend-side ``DATE_TRUNC`` (deferred to a future plan when data
 * volume outgrows the 200-row fetch cap).
 *
 * All math is UTC-stable: inputs are ISO timestamps, bucket keys are
 * YYYY-MM-DD strings computed in UTC. ISO weeks follow the ISO-8601
 * convention (Monday as the week start), which is what Grafana and
 * Postgres ``date_trunc('week', ...)`` also use.
 */

export const GRANULARITIES = ['day', 'week', 'month'] as const
export type Granularity = (typeof GRANULARITIES)[number]

export function isGranularity(value: unknown): value is Granularity {
  return typeof value === 'string' && (GRANULARITIES as readonly string[]).includes(value)
}

/**
 * Trailing-window size per granularity — how many buckets to render on a
 * chart by default. Day=30, Week=12, Month=12 roughly match "last month"
 * / "last quarter" / "last year" mental models.
 */
export function bucketCount(g: Granularity): number {
  switch (g) {
    case 'day':
      return 30
    case 'week':
      return 12
    case 'month':
      return 12
  }
}

function toUtcDate(dateIso: string): Date | null {
  const d = new Date(dateIso)
  return Number.isNaN(d.getTime()) ? null : d
}

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

/** YYYY-MM-DD for the given UTC day. */
function isoDayKey(d: Date): string {
  return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())}`
}

/**
 * Monday of the ISO-8601 week that contains ``d``. Uses UTC so a chart
 * rendered in a different timezone still shows the same week boundaries
 * the backend would compute.
 */
function isoWeekStart(d: Date): Date {
  const utc = new Date(
    Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()),
  )
  // getUTCDay: 0 Sun, 1 Mon, ... 6 Sat. ISO weeks start Monday, so shift.
  const dow = utc.getUTCDay()
  const daysFromMonday = (dow + 6) % 7 // Mon=0, Sun=6
  utc.setUTCDate(utc.getUTCDate() - daysFromMonday)
  return utc
}

/** YYYY-MM-01 for the first-of-month of ``d`` (UTC). */
function monthStartIso(d: Date): string {
  return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-01`
}

/**
 * Return the canonical bucket key for ``dateIso`` at the given
 * ``granularity``. Two dates that fall in the same bucket produce the
 * same key, so callers can use a plain ``Map<string, …>`` to aggregate.
 */
export function bucketStartIso(dateIso: string, g: Granularity): string | null {
  const d = toUtcDate(dateIso)
  if (!d) return null
  switch (g) {
    case 'day':
      return isoDayKey(d)
    case 'week':
      return isoDayKey(isoWeekStart(d))
    case 'month':
      return monthStartIso(d)
  }
}

const DAY_MONTH_FMT = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
})

const MONTH_YEAR_FMT = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
})

/** Human label for a bucket key. */
export function formatBucketLabel(bucketKey: string, g: Granularity): string {
  const d = toUtcDate(`${bucketKey}T00:00:00Z`)
  if (!d) return bucketKey

  switch (g) {
    case 'day':
      return DAY_MONTH_FMT.format(d)
    case 'month':
      return MONTH_YEAR_FMT.format(d)
    case 'week': {
      const end = new Date(d)
      end.setUTCDate(end.getUTCDate() + 6)
      return `${DAY_MONTH_FMT.format(d)} – ${DAY_MONTH_FMT.format(end)}`
    }
  }
}

export interface TrailingBucketPoint {
  bucket: string
  label: string
  value: number
  /** ISO timestamp of the bucket start — handy for tooltips / sorting. */
  bucketIso: string
}

/**
 * Bucket ``items`` by ``dateAccessor`` at the given ``granularity`` and
 * sum ``valueAccessor`` within each bucket. Returns buckets in ascending
 * chronological order. Items whose date fails to parse are dropped.
 *
 * A bucket with zero matching items is still emitted when it falls inside
 * the trailing window, so the x-axis reads continuously and empty periods
 * render as flat zero rather than a missing tick.
 */
export function trailingBuckets<T>(
  items: readonly T[],
  dateAccessor: (t: T) => string | undefined | null,
  valueAccessor: (t: T) => number,
  g: Granularity,
): TrailingBucketPoint[] {
  const totals = new Map<string, number>()

  for (const item of items) {
    const raw = dateAccessor(item)
    if (!raw) continue
    const key = bucketStartIso(raw, g)
    if (!key) continue
    const current = totals.get(key) ?? 0
    totals.set(key, current + valueAccessor(item))
  }

  // Fill any missing bucket between the earliest seen and now so the
  // x-axis doesn't skip empty periods.
  const keys = [...totals.keys()].sort()
  if (keys.length === 0) return []
  const filled = fillMissingBuckets(keys, g)

  return filled.map((key) => ({
    bucket: key,
    label: formatBucketLabel(key, g),
    value: totals.get(key) ?? 0,
    bucketIso: `${key}T00:00:00Z`,
  }))
}

function fillMissingBuckets(sortedKeys: string[], g: Granularity): string[] {
  if (sortedKeys.length <= 1) return sortedKeys

  const out: string[] = []
  let cursor = new Date(`${sortedKeys[0]}T00:00:00Z`)
  const end = new Date(`${sortedKeys[sortedKeys.length - 1]}T00:00:00Z`)

  while (cursor <= end) {
    out.push(bucketStartIso(cursor.toISOString(), g) ?? '')
    cursor = advance(cursor, g)
  }
  return out.filter(Boolean)
}

function advance(d: Date, g: Granularity): Date {
  const next = new Date(d)
  switch (g) {
    case 'day':
      next.setUTCDate(next.getUTCDate() + 1)
      break
    case 'week':
      next.setUTCDate(next.getUTCDate() + 7)
      break
    case 'month':
      next.setUTCMonth(next.getUTCMonth() + 1)
      break
  }
  return next
}
