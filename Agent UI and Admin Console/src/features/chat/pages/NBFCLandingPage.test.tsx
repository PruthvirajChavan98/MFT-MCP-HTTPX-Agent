import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NBFCLandingPage } from './NBFCLandingPage'

vi.mock('motion/react', async () => {
  const { motionReactMock } = await import('@/test/mocks/motion')
  return motionReactMock()
})

// The mock ChatWidget is rendered with the same data-highlight-id the real
// widget carries, so the attention-highlight hook measures a valid target.
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

/**
 * Most existing tests exercise the sequential spotlight tour, which now only
 * fires AFTER the attention highlight has been dismissed. Pre-set both the
 * disclaimer flag AND the attention-dismissed flag so those tests start from
 * the "user has seen the overview" state.
 */
function seedTourReady() {
  window.localStorage.setItem('mft_prototype_disclaimer_accepted_v1', 'true')
  window.localStorage.setItem('mft_landing_attention_dismissed_v1', 'true')
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  cleanup()
})

describe('NBFCLandingPage', () => {
  it('renders the CTA rail with matching pill geometry and opens the spotlight after disclaimer accepted', () => {
    seedTourReady()
    renderLandingPage()

    expect(getTourDialog()).toBeInTheDocument()
    expect(screen.getByText('Start with the main actions')).toBeInTheDocument()

    const ctaRail = document.querySelector('[data-highlight-id="landing-nav-ctas"]')
    expect(ctaRail).not.toBeNull()

    const scoped = within(ctaRail as HTMLElement)
    const adminLink = scoped.getByRole('link', { name: 'Admin' })
    expect(adminLink).toHaveClass('rounded-full', 'min-h-12')
    expect(adminLink).toHaveAttribute('href', '/admin')
    expect(adminLink).toHaveAttribute('data-highlight-id', 'landing-admin-btn')

    const registerBtn = scoped.getByRole('button', { name: 'Register' })
    expect(registerBtn).toHaveClass('rounded-full', 'min-h-12')
    expect(registerBtn).toHaveAttribute('data-highlight-id', 'landing-register-btn')

    const archLink = scoped.getByRole('link', { name: 'View Architecture' })
    expect(archLink).toHaveClass('rounded-full', 'min-h-12')
    expect(archLink).toHaveAttribute('href', '/architecture')
    expect(archLink).toHaveAttribute('data-highlight-id', 'landing-architecture-btn')
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
    seedTourReady()
    renderLandingPage()

    fireEvent.click(within(getTourDialog()).getByRole('button', { name: 'Next' }))
    expect(screen.getByText('Need help instantly?')).toBeInTheDocument()

    fireEvent.click(within(getTourDialog()).getByRole('button', { name: 'Done' }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /site tour/i })).not.toBeInTheDocument()
    })
    expect(window.localStorage.getItem('mft_landing_spotlight_dismissed_v1')).toBe('true')
  })

  // ────────────────────────────────────────────────────────────────────────
  // Attention highlight (one-shot showcase — fires before the spotlight)
  // ────────────────────────────────────────────────────────────────────────

  it('renders the attention highlight on the first visit with all four CTA cut-outs', () => {
    window.localStorage.setItem('mft_prototype_disclaimer_accepted_v1', 'true')
    renderLandingPage()

    const overlay = screen.getByTestId('landing-attention-highlight')
    expect(overlay).toBeInTheDocument()

    // A cut-out per target (admin, register, architecture, chat launcher).
    for (const id of [
      'landing-admin-btn',
      'landing-register-btn',
      'landing-architecture-btn',
      'landing-chat-launcher',
    ]) {
      expect(screen.getByTestId(`landing-attention-cutout-${id}`)).toBeInTheDocument()
    }

    // The sequential tour should NOT be open yet — attention runs first.
    expect(screen.queryByRole('dialog', { name: /site tour/i })).not.toBeInTheDocument()

    // The "demo page vs. real product" note sits above the dismiss button.
    const note = screen.getByTestId('landing-attention-note')
    expect(note).toHaveTextContent(/demo landing page/i)
    expect(note).toHaveTextContent(/agent/i)
    expect(note).toHaveTextContent(/admin console/i)
  })

  it('dismisses the attention highlight, persists localStorage, and then opens the spotlight', async () => {
    window.localStorage.setItem('mft_prototype_disclaimer_accepted_v1', 'true')
    renderLandingPage()

    fireEvent.click(screen.getByTestId('landing-attention-dismiss'))

    await waitFor(() => {
      expect(screen.queryByTestId('landing-attention-highlight')).not.toBeInTheDocument()
    })
    expect(window.localStorage.getItem('mft_landing_attention_dismissed_v1')).toBe('true')

    // Chained tour should now auto-open on the same visit.
    expect(getTourDialog()).toBeInTheDocument()
  })

  it('does not show the attention highlight on return visits', () => {
    window.localStorage.setItem('mft_prototype_disclaimer_accepted_v1', 'true')
    window.localStorage.setItem('mft_landing_attention_dismissed_v1', 'true')
    renderLandingPage()

    expect(screen.queryByTestId('landing-attention-highlight')).not.toBeInTheDocument()
  })

  it('forwards clicks on a highlighted CTA cut-out to the underlying button', async () => {
    window.localStorage.setItem('mft_prototype_disclaimer_accepted_v1', 'true')
    renderLandingPage()

    const underlyingAdmin = document.querySelector<HTMLAnchorElement>(
      '[data-highlight-id="landing-admin-btn"]',
    )
    expect(underlyingAdmin).not.toBeNull()
    const clickSpy = vi.fn()
    underlyingAdmin!.addEventListener('click', clickSpy)

    fireEvent.click(screen.getByTestId('landing-attention-cutout-landing-admin-btn'))

    // Overlay dismisses immediately.
    await waitFor(() => {
      expect(screen.queryByTestId('landing-attention-highlight')).not.toBeInTheDocument()
    })
    expect(window.localStorage.getItem('mft_landing_attention_dismissed_v1')).toBe('true')

    // Forwarded click fires after a microtask flush.
    await waitFor(() => expect(clickSpy).toHaveBeenCalled())
  })
})
