import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NBFCLandingPage } from './NBFCLandingPage'

vi.mock('motion/react', async () => {
  const { motionReactMock } = await import('@/test/mocks/motion')
  return motionReactMock()
})

vi.mock('../components/ChatWidget', () => ({
  ChatWidget: () => (
    <button aria-label="Open chat" data-highlight-id="landing-chat-launcher" type="button">
      Open chat
    </button>
  ),
}))

vi.mock('../components/RegisterDialog', () => ({
  RegisterDialog: () => null,
}))

function renderLandingPage() {
  return render(
    <MemoryRouter>
      <NBFCLandingPage />
    </MemoryRouter>,
  )
}

function getTourDialog() {
  return screen.getAllByRole('dialog', { name: /site tour/i })[0]
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  cleanup()
})

describe('NBFCLandingPage', () => {
  it('renders the CTA rail with matching pill geometry and opens the spotlight after disclaimer accepted', () => {
    window.localStorage.setItem('mft_prototype_disclaimer_accepted_v1', 'true')
    renderLandingPage()

    expect(getTourDialog()).toBeInTheDocument()
    expect(screen.getByText('Start with the main actions')).toBeInTheDocument()

    const ctaRail = document.querySelector('[data-highlight-id="landing-nav-ctas"]')
    expect(ctaRail).not.toBeNull()

    const scoped = within(ctaRail as HTMLElement)
    const adminLink = scoped.getByRole('link', { name: 'Admin' })
    expect(adminLink).toHaveClass('rounded-full', 'min-h-12')
    expect(adminLink).toHaveAttribute('href', '/admin')
    expect(scoped.getByRole('button', { name: 'Register' })).toHaveClass('rounded-full', 'min-h-12')
    const archLink = scoped.getByRole('link', { name: 'View Architecture' })
    expect(archLink).toHaveClass('rounded-full', 'min-h-12')
    expect(archLink).toHaveAttribute('href', '/architecture')
  })

  it('shows the admin demo notice on hover without changing navigation', async () => {
    window.localStorage.setItem('mft_register_notice_shown_v1', 'true')
    renderLandingPage()

    const adminLink = screen.getByRole('link', { name: 'Admin' })
    fireEvent.focus(adminLink)

    expect(await screen.findByText('Demo admin console')).toBeInTheDocument()
    expect(
      screen.getByText(
        'This admin area is part of the demo. Production-grade access controls can be added with OTP, MFA, or OAuth.',
      ),
    ).toBeInTheDocument()
    expect(adminLink).toHaveAttribute('href', '/admin')
  })

  it('advances the spotlight, persists dismissal, and supports manual reopen', async () => {
    window.localStorage.setItem('mft_prototype_disclaimer_accepted_v1', 'true')
    renderLandingPage()

    fireEvent.click(within(getTourDialog()).getByRole('button', { name: 'Next' }))
    expect(screen.getByText('Need help instantly?')).toBeInTheDocument()

    fireEvent.click(within(getTourDialog()).getByRole('button', { name: 'Done' }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /site tour/i })).not.toBeInTheDocument()
    })
    expect(window.localStorage.getItem('mft_landing_spotlight_dismissed_v1')).toBe('true')
  })
})
