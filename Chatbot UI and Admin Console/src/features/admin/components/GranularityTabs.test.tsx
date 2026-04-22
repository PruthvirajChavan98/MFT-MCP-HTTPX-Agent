import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useState } from 'react'
import type { Granularity } from '@features/admin/lib/time-bucket'
import { GranularityTabs, usePersistedGranularity } from './GranularityTabs'

function Harness({
  chartId,
  onChange,
}: {
  chartId?: string
  onChange?: (g: Granularity) => void
}) {
  const [value, setValue] = useState<Granularity>('day')
  return (
    <GranularityTabs
      chartId={chartId ?? 'test-chart'}
      value={value}
      onChange={(g) => {
        setValue(g)
        onChange?.(g)
      }}
    />
  )
}

function HookHarness({ chartId }: { chartId: string }) {
  const [value, setValue] = usePersistedGranularity(chartId)
  return (
    <div>
      <span data-testid="current-value">{value}</span>
      <GranularityTabs chartId={chartId} value={value} onChange={setValue} />
    </div>
  )
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  cleanup()
})

describe('GranularityTabs', () => {
  it('renders three pill tabs with ARIA roles', () => {
    render(<Harness />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(3)
    expect(tabs[0]).toHaveTextContent('Daily')
    expect(tabs[1]).toHaveTextContent('Weekly')
    expect(tabs[2]).toHaveTextContent('Monthly')
  })

  it('marks the selected tab with aria-selected=true and tabIndex=0', () => {
    render(<Harness />)
    const [day, week, month] = screen.getAllByRole('tab')
    expect(day).toHaveAttribute('aria-selected', 'true')
    expect(day).toHaveAttribute('tabindex', '0')
    expect(week).toHaveAttribute('aria-selected', 'false')
    expect(week).toHaveAttribute('tabindex', '-1')
    expect(month).toHaveAttribute('aria-selected', 'false')
  })

  it('invokes onChange when a tab is clicked', () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Weekly' }))
    expect(onChange).toHaveBeenCalledWith('week')
  })

  it('cycles tabs with ArrowRight / ArrowLeft keys', () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)
    const day = screen.getByRole('tab', { name: 'Daily' })
    fireEvent.keyDown(day, { key: 'ArrowRight' })
    expect(onChange).toHaveBeenLastCalledWith('week')

    const week = screen.getByRole('tab', { name: 'Weekly' })
    fireEvent.keyDown(week, { key: 'ArrowLeft' })
    expect(onChange).toHaveBeenLastCalledWith('day')
  })

  it('wraps around at the edges', () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Daily' }), { key: 'ArrowLeft' })
    expect(onChange).toHaveBeenLastCalledWith('month')
  })

  it('announces itself with an aria-label on the tablist', () => {
    render(<Harness />)
    const list = screen.getByRole('tablist')
    expect(list).toHaveAttribute('aria-label', 'Chart granularity')
  })
})

describe('usePersistedGranularity', () => {
  it('defaults to day when nothing is in localStorage', () => {
    render(<HookHarness chartId="volatile-chart" />)
    expect(screen.getByTestId('current-value')).toHaveTextContent('day')
  })

  it('hydrates from localStorage on mount', () => {
    window.localStorage.setItem('mft_admin_granularity_recalled-chart_v1', 'week')
    render(<HookHarness chartId="recalled-chart" />)
    expect(screen.getByTestId('current-value')).toHaveTextContent('week')
  })

  it('persists a click-driven change to localStorage', () => {
    render(<HookHarness chartId="persist-me" />)
    fireEvent.click(screen.getByRole('tab', { name: 'Monthly' }))
    expect(screen.getByTestId('current-value')).toHaveTextContent('month')
    expect(window.localStorage.getItem('mft_admin_granularity_persist-me_v1')).toBe('month')
  })

  it('keeps per-chart state independent', () => {
    window.localStorage.setItem('mft_admin_granularity_chart-a_v1', 'week')
    window.localStorage.setItem('mft_admin_granularity_chart-b_v1', 'month')
    render(
      <>
        <HookHarness chartId="chart-a" />
        <HookHarness chartId="chart-b" />
      </>,
    )
    const spans = screen.getAllByTestId('current-value')
    expect(spans[0]).toHaveTextContent('week')
    expect(spans[1]).toHaveTextContent('month')
  })

  it('ignores a malformed stored value and falls back to the default', () => {
    window.localStorage.setItem('mft_admin_granularity_garbage-chart_v1', 'hourly')
    render(<HookHarness chartId="garbage-chart" />)
    expect(screen.getByTestId('current-value')).toHaveTextContent('day')
  })
})
