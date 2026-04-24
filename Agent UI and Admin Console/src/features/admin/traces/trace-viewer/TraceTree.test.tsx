import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { TraceTree } from './TraceTree'
import type { FlatNode } from './types'

const NODES: FlatNode[] = [
  {
    id: 'root',
    type: 'trace',
    name: 'Root Trace',
    latencyS: '0.42',
    status: 'success',
    tokens: 128,
    depth: 0,
  },
]

describe('TraceTree', () => {
  it(
    'renders a back button in the header and calls onClose when clicked',
    () => {
      const onClose = vi.fn()

      render(
        <TraceTree
          nodes={NODES}
          selectedNodeId="root"
          onSelect={vi.fn()}
          onClose={onClose}
          isLoading={false}
        />,
      )

      const backButton = screen.getByRole('button', { name: 'Back to traces' })
      expect(backButton).toHaveTextContent('Back')
      fireEvent.click(backButton)

      expect(onClose).toHaveBeenCalledTimes(1)
    },
    15000,
  )

  it('renders a back arrow instead of the previous close icon', () => {
    const { container } = render(
      <TraceTree
        nodes={NODES}
        selectedNodeId="root"
        onSelect={vi.fn()}
        onClose={vi.fn()}
        isLoading={false}
      />,
    )

    expect(container.querySelector('.lucide-arrow-left')).toBeTruthy()
    expect(container.querySelector('.lucide-minimize-2')).toBeNull()
    expect(container.querySelector('.lucide-x')).toBeNull()
  })
})
