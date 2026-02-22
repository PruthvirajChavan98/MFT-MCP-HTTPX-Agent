import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(() => ({ data: { items: [], total: 0, count: 0, offset: 0, limit: 25 }, isLoading: false, error: null })),
}))

vi.mock('./AdminContext', () => ({
  useAdminContext: vi.fn(() => ({ adminKey: '', setAdminKey: vi.fn(), openrouterKey: '', setOpenrouterKey: vi.fn(), groqKey: '', setGroqKey: vi.fn() })),
}))

describe('Guardrails page states', () => {
  it('shows admin key requirement when key is missing', async () => {
    const { Guardrails } = await import('./Guardrails')
    render(<Guardrails />)
    expect(screen.getByText(/Set X-Admin-Key to view guardrail events/i)).toBeInTheDocument()
  })
})
