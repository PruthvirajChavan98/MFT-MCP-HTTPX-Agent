import { useCallback, useEffect, useRef, useState } from 'react'
import { GRANULARITIES, isGranularity, type Granularity } from '@features/admin/lib/time-bucket'

const STORAGE_KEY_PREFIX = 'mft_admin_granularity_'
const STORAGE_KEY_SUFFIX = '_v1'

const LABELS: Record<Granularity, string> = {
  day: 'Daily',
  week: 'Weekly',
  month: 'Monthly',
}

function storageKeyFor(chartId: string): string {
  return `${STORAGE_KEY_PREFIX}${chartId}${STORAGE_KEY_SUFFIX}`
}

function readPersistedGranularity(chartId: string): Granularity | null {
  try {
    const raw = window.localStorage.getItem(storageKeyFor(chartId))
    return isGranularity(raw) ? raw : null
  } catch {
    return null
  }
}

function persistGranularity(chartId: string, value: Granularity): void {
  try {
    window.localStorage.setItem(storageKeyFor(chartId), value)
  } catch {
    // localStorage unavailable — silently skip.
  }
}

interface GranularityTabsProps {
  /**
   * Stable identifier for this chart's granularity. Two charts on the same
   * page with distinct IDs get independent persistence so an operator's
   * Weekly choice on one chart doesn't flip the other.
   */
  chartId: string
  value: Granularity
  onChange: (next: Granularity) => void
  /** Optional label read by screen readers before the tab list. */
  ariaLabel?: string
}

/**
 * Three-pill tab group for daily / weekly / monthly chart granularity.
 *
 * Matches the existing `rounded-full border border-primary/20
 * bg-primary/10 text-primary` accent used for chip-style indicators on the
 * chart headers (e.g. the "12 SESSIONS" badge on ChatCostsPage).
 *
 * Keyboard: `role="tablist"` with arrow keys cycling through tabs
 * — standard ARIA tab pattern.
 */
export function GranularityTabs({
  chartId,
  value,
  onChange,
  ariaLabel = 'Chart granularity',
}: GranularityTabsProps) {
  const refs = useRef<Array<HTMLButtonElement | null>>([])

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
      event.preventDefault()
      const delta = event.key === 'ArrowRight' ? 1 : -1
      const nextIndex = (index + delta + GRANULARITIES.length) % GRANULARITIES.length
      const nextValue = GRANULARITIES[nextIndex]
      onChange(nextValue)
      refs.current[nextIndex]?.focus()
    },
    [onChange],
  )

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/5 p-0.5"
    >
      {GRANULARITIES.map((g, index) => {
        const selected = g === value
        return (
          <button
            key={g}
            ref={(el) => {
              refs.current[index] = el
            }}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            data-granularity={g}
            onClick={() => onChange(g)}
            onKeyDown={(e) => handleKeyDown(e, index)}
            className={`rounded-full px-3 py-1 text-[11px] font-tabular uppercase tracking-[0.15em] transition-colors ${
              selected
                ? 'bg-primary/20 text-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {LABELS[g]}
          </button>
        )
      })}
    </div>
  )
}

/**
 * Hook that reads + persists a per-chart granularity preference in
 * localStorage. Returns a `[value, setValue]` tuple suitable for passing
 * straight into `<GranularityTabs>`.
 */
export function usePersistedGranularity(
  chartId: string,
  defaultValue: Granularity = 'day',
): [Granularity, (next: Granularity) => void] {
  const [value, setValue] = useState<Granularity>(() => {
    return readPersistedGranularity(chartId) ?? defaultValue
  })

  // Persist on change. The initial read already loaded any prior choice,
  // so the first render never writes (prevents thrashing localStorage on
  // every mount of a new chart).
  const mounted = useRef(false)
  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true
      return
    }
    persistGranularity(chartId, value)
  }, [chartId, value])

  return [value, setValue]
}
