import { cleanup, render, screen } from '@testing-library/react'
import { Activity } from 'lucide-react'
import { afterEach, describe, expect, it } from 'vitest'

import { StatCard } from './StatCard'

describe('StatCard', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders label and value', () => {
    render(<StatCard label="Active Sessions" value="42" />)
    expect(screen.getByText('Active Sessions')).toBeTruthy()
    expect(screen.getByText('42')).toBeTruthy()
  })

  it('applies font-tabular to the value for column-aligned numerics', () => {
    render(<StatCard label="Requests" value={1234} />)
    const valueEl = screen.getByText('1234')
    expect(valueEl.className).toMatch(/font-tabular/)
  })

  it('renders the icon when provided', () => {
    render(<StatCard label="Active" value="1" icon={Activity} />)
    // Lucide icons render as SVGs with a data-slot or role
    const svg = document.querySelector('svg')
    expect(svg).toBeTruthy()
  })

  it('renders an optional hint line', () => {
    render(<StatCard label="Cost" value="$12.34" hint="last 24 hours" />)
    expect(screen.getByText('last 24 hours')).toBeTruthy()
  })

  it('applies tone classes for non-default tones', () => {
    const { container } = render(
      <StatCard label="Errors" value="3" icon={Activity} tone="destructive" />,
    )
    // Tone affects the icon container, not the value — find the icon wrapper
    const iconWrapper = container.querySelector('[aria-hidden="true"]')
    expect(iconWrapper?.className).toMatch(/text-destructive/)
  })
})
