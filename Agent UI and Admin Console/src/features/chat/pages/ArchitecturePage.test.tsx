import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ArchitecturePage } from './ArchitecturePage'
import { TOOL_COUNT } from './architecture'

vi.mock('motion/react', async () => {
  const { motionReactMock } = await import('@/test/mocks/motion')
  return motionReactMock()
})

afterEach(() => {
  cleanup()
})

function renderPage() {
  return render(
    <MemoryRouter>
      <ArchitecturePage />
    </MemoryRouter>,
  )
}

const EXPECTED_ANCHOR_IDS = [
  'hero',
  'topology',
  'lifecycle',
  'inline-guard',
  'langgraph',
  'mcp',
  'crm',
  'frontend',
  'walkthroughs',
  'eval-store',
  'security',
  'observability',
  'deployment',
  'principles',
] as const

describe('ArchitecturePage', () => {
  it('renders the hero with the gradient title and three stat cards', () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/architecture, end-to-end/i)
    expect(screen.getByText('MCP tools')).toBeInTheDocument()
    expect(screen.getByText('Processes')).toBeInTheDocument()
    expect(screen.getByText('Checkpointer TTL')).toBeInTheDocument()
  })

  it('mounts every section anchor referenced by the right-rail TOC', () => {
    renderPage()
    EXPECTED_ANCHOR_IDS.forEach((id) => {
      const section = document.getElementById(id)
      expect(section, `section #${id} should exist`).not.toBeNull()
    })
  })

  it('renders the tool table with one row per tool catalogue entry', () => {
    renderPage()
    const mcpSection = document.getElementById('mcp')
    expect(mcpSection).not.toBeNull()
    const toolTable = within(mcpSection as HTMLElement).getByRole('table')
    const tbody = toolTable.querySelector('tbody')
    expect(tbody).not.toBeNull()
    const rows = within(tbody as HTMLElement).getAllByRole('row')
    expect(rows.length).toBe(TOOL_COUNT)
  })

  it('renders three live walkthrough cards with their titles', () => {
    renderPage()
    expect(
      screen.getByRole('heading', { level: 3, name: /public path · otp send/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 3, name: /inline-guard block/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 3, name: /session-gated path · loan dashboard/i }),
    ).toBeInTheDocument()
  })

  it('exposes copy buttons that invoke navigator.clipboard.writeText', () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(window.navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })

    renderPage()
    const buttons = screen.getAllByRole('button', { name: /^copy/i })
    expect(buttons.length).toBeGreaterThan(0)
    fireEvent.click(buttons[0])
    expect(writeText).toHaveBeenCalledTimes(1)
  })

  it('folds consecutive token frames into one timeline beat in the lifecycle section', () => {
    renderPage()
    const lifecycle = document.getElementById('lifecycle')
    expect(lifecycle).not.toBeNull()
    // Walkthrough A has 4 consecutive token frames; the timeline must collapse
    // them into a single beat carrying a `×4` count indicator.
    const folded = within(lifecycle as HTMLElement).getByText('×4')
    expect(folded).toBeInTheDocument()
  })
})
