import { Menu, X } from 'lucide-react'
import { motion, useInView } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@components/ui/hover-card'
import { DISCLAIMER_ACCEPTED_EVENT, DISCLAIMER_ACCEPTED_KEY } from '@components/PrototypeDisclaimer'
import { ChatWidget } from '../components/ChatWidget'
import { RegisterDialog } from '../components/RegisterDialog'
import {
  FEATURES,
  LANDING_ATTENTION_STORAGE_KEY,
  LANDING_ATTENTION_TARGETS,
  LANDING_SPOTLIGHT_STEPS,
  LANDING_SPOTLIGHT_STORAGE_KEY,
  LOAN_PRODUCTS,
  STATS,
} from './landing-data'

/**
 * Poll the bounding rects of multiple `data-highlight-id` targets.
 *
 * Shared by `LandingSpotlightTour` (single-target) and
 * `LandingAttentionHighlight` (multi-target). Re-measures on mount, window
 * resize, and scroll so layout changes (disclaimer dismissing, font loading,
 * mobile orientation change) keep cut-outs aligned with their targets.
 *
 * Returns a Map keyed by `data-highlight-id`; entries are omitted when the
 * DOM element is missing or the rect is empty (off-screen / `display:none`),
 * so callers can safely iterate without a null-check.
 */
function useTargetRects(ids: readonly string[], enabled: boolean): Map<string, DOMRect> {
  const [rects, setRects] = useState<Map<string, DOMRect>>(() => new Map())
  // Serialize the ids into a primitive so React's dep-comparison fires the
  // effect whenever the set of targets changes — the spotlight tour swaps
  // target IDs as the user advances steps, and the previous stable-ref
  // shortcut caused the effect to stick on the first step's target.
  const idsKey = ids.join('|')

  useEffect(() => {
    if (!enabled) return

    const update = () => {
      const next = new Map<string, DOMRect>()
      for (const id of idsKey.split('|').filter(Boolean)) {
        const el = document.querySelector<HTMLElement>(`[data-highlight-id="${id}"]`)
        if (!el) continue
        next.set(id, el.getBoundingClientRect())
      }
      setRects(next)
    }

    update()
    window.addEventListener('resize', update)
    window.addEventListener('scroll', update, true)
    return () => {
      window.removeEventListener('resize', update)
      window.removeEventListener('scroll', update, true)
    }
  }, [enabled, idsKey])

  return rects
}

const CTA_GEOMETRY =
  'inline-flex min-h-12 items-center justify-center rounded-full px-6 text-sm font-semibold tracking-tight transition-all duration-200'

const CTA_PRIMARY =
  `${CTA_GEOMETRY} min-w-[10.5rem] bg-gradient-to-r from-teal-500 to-cyan-600 text-white shadow-[0_18px_40px_-24px_rgba(34,211,238,0.9)] hover:opacity-95`

const CTA_SECONDARY =
  `${CTA_GEOMETRY} min-w-[10.5rem] border border-teal-400/35 bg-white/5 text-teal-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] hover:border-teal-300/60 hover:bg-teal-400/10 hover:text-white`

// ─── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ value, label, index }: { value: string; label: string; index: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true })

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ delay: index * 0.1, duration: 0.5 }}
      className="text-center"
    >
      <div className="text-3xl font-bold text-teal-400 sm:text-4xl">{value}</div>
      <div className="mt-1 text-sm text-slate-400">{label}</div>
    </motion.div>
  )
}

function LoanCard({
  product,
  index,
}: {
  product: (typeof LOAN_PRODUCTS)[number]
  index: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true })

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 30 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ delay: index * 0.12, duration: 0.5 }}
      whileHover={{ y: -6, transition: { duration: 0.2 } }}
      className={`group relative flex flex-col rounded-2xl border border-white/10 bg-slate-800/60 p-6 backdrop-blur-sm transition-all duration-300 ${product.border}`}
    >
      {product.badge && (
        <span className="absolute -top-3 right-5 rounded-full bg-teal-500 px-3 py-0.5 text-xs font-semibold text-white shadow-md">
          {product.badge}
        </span>
      )}

      {/* Icon gradient strip */}
      <div
        className={`mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${product.accent} text-2xl shadow-lg`}
      >
        {product.icon}
      </div>

      <h3 className="text-xl font-bold text-white">{product.title}</h3>
      <p className="mt-0.5 text-sm text-slate-400">{product.subtitle}</p>

      {/* Rate */}
      <div className="mt-4 flex items-baseline gap-1">
        <span className={`text-3xl font-extrabold bg-gradient-to-r ${product.accent} bg-clip-text text-transparent`}>
          {product.rate}
        </span>
        <span className="text-xs text-slate-400">{product.rateLabel}</span>
      </div>

      {/* Feature list */}
      <ul className="mt-4 space-y-2 flex-1">
        {product.features.map((f) => (
          <li key={f} className="flex items-center gap-2 text-sm text-slate-300">
            <span className="h-1.5 w-1.5 rounded-full bg-teal-400 flex-shrink-0" />
            {f}
          </li>
        ))}
      </ul>

      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className={`mt-6 w-full rounded-xl bg-gradient-to-r ${product.accent} py-2.5 text-sm font-semibold text-white shadow-md transition-opacity hover:opacity-90`}
      >
        Apply Now
      </motion.button>
    </motion.div>
  )
}

function FeatureCard({ icon, title, desc, index }: { icon: string; title: string; desc: string; index: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true })

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ delay: (index % 3) * 0.1, duration: 0.45 }}
      className="group rounded-2xl border border-white/5 bg-slate-800/40 p-6 backdrop-blur-sm transition-colors hover:border-teal-500/30 hover:bg-slate-800/70"
    >
      <div className="mb-3 text-3xl">{icon}</div>
      <h4 className="font-semibold text-white">{title}</h4>
      <p className="mt-2 text-sm leading-relaxed text-slate-400">{desc}</p>
    </motion.div>
  )
}

function LandingSpotlightTour({
  isOpen,
  stepIndex,
  onBack,
  onNext,
  onClose,
}: {
  isOpen: boolean
  stepIndex: number
  onBack: () => void
  onNext: () => void
  onClose: () => void
}) {
  const step = LANDING_SPOTLIGHT_STEPS[stepIndex]
  // useTargetRects serialises ids internally so we can pass a fresh array
  // each render without rebuilding the effect gratuitously.
  const rects = useTargetRects([step.targetId], isOpen)
  const targetRect = rects.get(step.targetId) ?? null

  if (!isOpen) return null

  const viewportWidth = typeof window === 'undefined' ? 1280 : window.innerWidth
  const viewportHeight = typeof window === 'undefined' ? 720 : window.innerHeight
  const cardWidth = Math.min(360, viewportWidth - 32)
  const rect = targetRect

  const cardLeft = rect
    ? Math.min(Math.max(16, rect.left), Math.max(16, viewportWidth - cardWidth - 16))
    : 16
  const preferredTop = rect ? rect.bottom + 20 : 24
  const cardTop =
    preferredTop + 220 > viewportHeight && rect
      ? Math.max(16, rect.top - 236)
      : Math.min(preferredTop, Math.max(16, viewportHeight - 236))

  return (
    <div aria-label="Site tour" aria-modal="true" className="fixed inset-0 z-[80]" role="dialog">
      <div className="absolute inset-0 bg-slate-950/72 backdrop-blur-[2px]" />

      {rect && (
        <div
          aria-hidden
          className="pointer-events-none fixed rounded-[30px] border-2 border-cyan-300/80 shadow-[0_0_0_9999px_rgba(2,6,23,0.58),0_0_0_10px_rgba(34,211,238,0.14)] transition-all duration-200"
          style={{
            top: Math.max(8, rect.top - 10),
            left: Math.max(8, rect.left - 10),
            width: rect.width + 20,
            height: rect.height + 20,
          }}
        />
      )}

      <div
        className="fixed rounded-[28px] border border-white/10 bg-slate-950/96 p-5 text-white shadow-2xl"
        style={{
          top: cardTop,
          left: cardLeft,
          width: cardWidth,
        }}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-cyan-200">
              Step {stepIndex + 1} of {LANDING_SPOTLIGHT_STEPS.length}
            </div>
            <h2 className="mt-3 text-lg font-semibold tracking-tight">{step.title}</h2>
          </div>
          <button
            className="inline-flex min-h-9 items-center justify-center rounded-full border border-white/10 bg-white/5 px-3 text-xs font-semibold text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
            onClick={onClose}
            type="button"
          >
            Skip
          </button>
        </div>

        <p className="mt-3 text-sm leading-6 text-slate-300">{step.description}</p>

        <div className="mt-5 flex items-center justify-between gap-3">
          <button
            className="inline-flex min-h-11 items-center justify-center rounded-full border border-white/10 px-4 text-sm font-medium text-slate-300 transition-colors hover:bg-white/10 hover:text-white disabled:opacity-40"
            disabled={stepIndex === 0}
            onClick={onBack}
            type="button"
          >
            Back
          </button>

          <div className="flex items-center gap-2">
            {LANDING_SPOTLIGHT_STEPS.map((tourStep) => (
              <span
                key={tourStep.targetId}
                aria-hidden
                className={`h-2 rounded-full transition-all ${
                  tourStep.targetId === step.targetId ? 'w-8 bg-cyan-300' : 'w-2 bg-white/20'
                }`}
              />
            ))}
          </div>

          <button
            className="inline-flex min-h-11 items-center justify-center rounded-full bg-gradient-to-r from-teal-500 to-cyan-600 px-5 text-sm font-semibold text-white shadow-[0_18px_40px_-24px_rgba(34,211,238,0.9)] transition-opacity hover:opacity-95"
            onClick={onNext}
            type="button"
          >
            {stepIndex === LANDING_SPOTLIGHT_STEPS.length - 1 ? 'Done' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  )
}

const LANDING_ATTENTION_TARGET_IDS = LANDING_ATTENTION_TARGETS.map((t) => t.id)

/**
 * First-visit attention showcase. Dims the rest of the page with a soft
 * backdrop and highlights all four key CTAs simultaneously (Admin, Register,
 * Architecture, Chat launcher), letting a visitor see every key flow at
 * once without stepping through a sequential tour.
 *
 * Dismisses via a "Got it" button OR by clicking any highlighted target
 * (the click forwards through to the underlying element, so the overlay
 * doubles as a navigation affordance). Persists the dismissal under
 * ``LANDING_ATTENTION_STORAGE_KEY`` — once dismissed, never shown again
 * on the same browser profile.
 */
function LandingAttentionHighlight({
  isOpen,
  onDismiss,
}: {
  isOpen: boolean
  onDismiss: () => void
}) {
  const rects = useTargetRects(LANDING_ATTENTION_TARGET_IDS, isOpen)

  if (!isOpen) return null

  const forwardClickTo = (id: string) => {
    const el = document.querySelector<HTMLElement>(`[data-highlight-id="${id}"]`)
    onDismiss()
    // Fire the underlying click after dismiss so the navigation uses the
    // post-dismiss state (overlay removed, no z-index blocking). queueMicrotask
    // is enough — React commit finishes before the microtask drains.
    if (el) queueMicrotask(() => el.click())
  }

  return (
    <div
      aria-label="Landing highlights"
      aria-modal="true"
      className="fixed inset-0 z-[75]"
      role="dialog"
      data-testid="landing-attention-highlight"
    >
      <div
        aria-hidden
        className="absolute inset-0 bg-slate-950/60 backdrop-blur-[2px]"
        onClick={onDismiss}
      />

      {LANDING_ATTENTION_TARGETS.map((target) => {
        const rect = rects.get(target.id)
        if (!rect) return null
        return (
          <button
            key={target.id}
            type="button"
            aria-label={`Go to ${target.label}`}
            data-testid={`landing-attention-cutout-${target.id}`}
            className="absolute cursor-pointer rounded-[28px] border-2 border-cyan-300/80 shadow-[0_0_0_4px_rgba(34,211,238,0.18)] transition-all duration-200 hover:border-cyan-200 hover:shadow-[0_0_0_6px_rgba(34,211,238,0.28)]"
            style={{
              top: Math.max(6, rect.top - 8),
              left: Math.max(6, rect.left - 8),
              width: rect.width + 16,
              height: rect.height + 16,
            }}
            onClick={() => forwardClickTo(target.id)}
          />
        )
      })}

      <div className="pointer-events-none absolute inset-x-0 bottom-16 flex flex-col items-center gap-3 px-4">
        <div
          data-testid="landing-attention-note"
          className="pointer-events-auto max-w-xl rounded-2xl border border-white/10 bg-slate-950/85 px-5 py-3 text-center shadow-[0_20px_50px_-28px_rgba(34,211,238,0.6)] backdrop-blur-md"
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-300">
            Demo landing page
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-slate-200">
            This marketing page is scaffolding. The real product is the{' '}
            <span className="font-semibold text-white">Agent</span> (chat widget) and the{' '}
            <span className="font-semibold text-white">Admin Console</span> — both highlighted
            above.
          </p>
        </div>

        <button
          type="button"
          onClick={onDismiss}
          data-testid="landing-attention-dismiss"
          className="pointer-events-auto inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-white/10 bg-slate-950/90 px-5 text-sm font-semibold text-slate-100 shadow-[0_20px_50px_-28px_rgba(34,211,238,0.7)] backdrop-blur-md transition-colors hover:bg-slate-900/95 hover:text-white"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-300 animate-pulse" />
          Got it — show me around
        </button>
      </div>
    </div>
  )
}

// ─── Main component ────────────────────────────────────────────────────────────

export function NBFCLandingPage() {
  const [registerOpen, setRegisterOpen] = useState(false)
  const [registerNoticeOpen, setRegisterNoticeOpen] = useState(
    () => !localStorage.getItem('mft_register_notice_shown_v1'),
  )
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [isSpotlightOpen, setIsSpotlightOpen] = useState(false)
  const [spotlightStepIndex, setSpotlightStepIndex] = useState(0)
  const [isAttentionOpen, setIsAttentionOpen] = useState(false)

  useEffect(() => {
    // Attention highlight shows FIRST (one-shot, simultaneous). The sequential
    // spotlight tour only fires AFTER attention is dismissed so the two
    // overlays don't stack on the same visit.
    const maybeOpenAttention = () => {
      try {
        const disclaimerAccepted = window.localStorage.getItem(DISCLAIMER_ACCEPTED_KEY) === 'true'
        if (!disclaimerAccepted) return
        if (window.localStorage.getItem(LANDING_ATTENTION_STORAGE_KEY) === 'true') return
        setIsAttentionOpen(true)
      } catch {
        // localStorage unavailable -- skip the overlay entirely.
      }
    }

    const maybeOpenSpotlight = () => {
      try {
        const disclaimerAccepted = window.localStorage.getItem(DISCLAIMER_ACCEPTED_KEY) === 'true'
        if (!disclaimerAccepted) return
        // Hold the spotlight until the attention highlight has been seen.
        if (window.localStorage.getItem(LANDING_ATTENTION_STORAGE_KEY) !== 'true') return
        if (window.localStorage.getItem(LANDING_SPOTLIGHT_STORAGE_KEY) !== 'true') {
          setIsSpotlightOpen(true)
        }
      } catch {
        // localStorage unavailable -- don't open the spotlight
      }
    }

    const maybeOpenAny = () => {
      maybeOpenAttention()
      maybeOpenSpotlight()
    }

    // If the disclaimer was already accepted on a previous visit, open immediately.
    maybeOpenAny()

    // If the disclaimer is dismissed during this session, open after it closes.
    window.addEventListener(DISCLAIMER_ACCEPTED_EVENT, maybeOpenAny)
    return () => window.removeEventListener(DISCLAIMER_ACCEPTED_EVENT, maybeOpenAny)
  }, [])

  const closeAttention = () => {
    setIsAttentionOpen(false)
    try {
      window.localStorage.setItem(LANDING_ATTENTION_STORAGE_KEY, 'true')
    } catch {
      // localStorage can be unavailable in restricted environments.
    }
    // Chain into the spotlight tour if the visitor hasn't seen it yet.
    try {
      if (window.localStorage.getItem(LANDING_SPOTLIGHT_STORAGE_KEY) !== 'true') {
        setIsSpotlightOpen(true)
      }
    } catch {
      // localStorage unavailable -- skip the chained tour.
    }
  }

  const closeSpotlight = () => {
    setIsSpotlightOpen(false)
    try {
      window.localStorage.setItem(LANDING_SPOTLIGHT_STORAGE_KEY, 'true')
    } catch {
      // localStorage can be unavailable in restricted environments.
    }
  }

  const advanceSpotlight = () => {
    if (spotlightStepIndex >= LANDING_SPOTLIGHT_STEPS.length - 1) {
      closeSpotlight()
      return
    }
    setSpotlightStepIndex((current) => current + 1)
  }

  return (
    <div className="min-h-screen overflow-x-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* ── Nav ── */}
      <nav className="sticky top-0 z-40 border-b border-white/5 bg-slate-950/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-teal-500 to-cyan-600 font-bold text-white text-sm shadow">
              MFT
            </div>
            <span className="text-lg font-bold tracking-tight">Mock FinTech</span>
          </div>

          <button
            className="md:hidden inline-flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 transition-colors hover:text-white"
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            aria-label="Toggle menu"
            type="button"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>

          <div className="hidden items-center gap-8 md:flex">
            {['Home Loans', 'Business Loans', 'Personal Loans', 'Rates'].map((item) => (
              <a key={item} href="#" className="text-sm text-slate-400 transition-colors hover:text-white">
                {item}
              </a>
            ))}
          </div>

          <div data-highlight-id="landing-nav-ctas" className="hidden md:flex items-center gap-3">
            <HoverCard openDelay={0} closeDelay={120}>
              <HoverCardTrigger asChild>
                <Link
                  to="/admin"
                  data-highlight-id="landing-admin-btn"
                  className={`hidden md:inline-flex ${CTA_GEOMETRY} min-w-[8.75rem] border border-orange-400/35 bg-orange-500/10 text-orange-300 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] hover:border-orange-300/60 hover:bg-orange-400/20 hover:text-orange-100`}
                >
                  Admin
                </Link>
              </HoverCardTrigger>
              <HoverCardContent
                align="center"
                side="bottom"
                className="z-[70] w-80 border-white/10 bg-slate-950/95 p-4 text-slate-100 shadow-[0_24px_60px_-32px_rgba(15,23,42,0.95)] backdrop-blur-xl"
              >
                <p className="text-sm font-semibold text-white">Demo admin console</p>
                <p className="mt-2 text-sm leading-relaxed text-slate-300">
                  This admin area is part of the demo. Production-grade access controls can
                  be added with OTP, MFA, or OAuth.
                </p>
              </HoverCardContent>
            </HoverCard>
            <HoverCard
              open={registerNoticeOpen || undefined}
              onOpenChange={(open) => {
                if (!open) {
                  setRegisterNoticeOpen(false)
                  localStorage.setItem('mft_register_notice_shown_v1', 'true')
                }
              }}
              openDelay={0}
              closeDelay={120}
            >
              <HoverCardTrigger asChild>
                <motion.button
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => setRegisterOpen(true)}
                  data-highlight-id="landing-register-btn"
                  className={`hidden md:inline-flex ${CTA_SECONDARY}`}
                >
                  Register
                </motion.button>
              </HoverCardTrigger>
              <HoverCardContent
                align="center"
                side="bottom"
                className="z-[70] w-80 border-white/10 bg-slate-950/95 p-4 text-slate-100 shadow-[0_24px_60px_-32px_rgba(15,23,42,0.95)] backdrop-blur-xl"
              >
                <p className="text-sm font-semibold text-white">Demo registration</p>
                <p className="mt-2 text-sm leading-relaxed text-slate-300">
                  Register with any 10-digit mobile number to explore the full demo — loan
                  dashboards, document downloads, and AI-assisted servicing. No real data is stored.
                </p>
              </HoverCardContent>
            </HoverCard>
            <Link
              to="/architecture"
              data-highlight-id="landing-architecture-btn"
              className={`hidden md:inline-flex ${CTA_PRIMARY}`}
            >
              View Architecture
            </Link>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-white/5 bg-slate-950/95 backdrop-blur-xl px-6 py-4 space-y-2">
            <Link
              to="/admin"
              onClick={() => setMobileMenuOpen(false)}
              className="block w-full rounded-full border border-orange-400/35 bg-orange-500/10 px-4 py-2.5 text-center text-sm font-semibold text-orange-300 transition-colors hover:bg-orange-400/20"
            >
              Admin
            </Link>
            <button
              onClick={() => { setRegisterOpen(true); setMobileMenuOpen(false) }}
              className="block w-full rounded-full border border-teal-400/35 bg-white/5 px-4 py-2.5 text-center text-sm font-semibold text-teal-200 transition-colors hover:bg-teal-400/10"
              type="button"
            >
              Register
            </button>
            <Link
              to="/architecture"
              onClick={() => setMobileMenuOpen(false)}
              className="block w-full rounded-full bg-gradient-to-r from-teal-500 to-cyan-600 px-4 py-2.5 text-center text-sm font-semibold text-white shadow-lg"
            >
              View Architecture
            </Link>
          </div>
        )}
      </nav>

      {/* ── Hero ── */}
      <section className="relative overflow-hidden px-6 pb-24 pt-20 sm:pb-32 sm:pt-28">
        {/* Background radial glow */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="h-[600px] w-[600px] rounded-full bg-teal-500/10 blur-[120px]" />
        </div>

        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mb-4 inline-flex items-center gap-2 rounded-full border border-teal-500/30 bg-teal-500/10 px-4 py-1.5 text-sm text-teal-300"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-teal-400 animate-pulse" />
            Non-RBI Registered NBFC • Trusted Since 2005
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.6 }}
            className="text-4xl font-extrabold leading-tight tracking-tight sm:text-6xl"
          >
            Financial Solutions{' '}
            <span className="bg-gradient-to-r from-teal-400 to-cyan-400 bg-clip-text text-transparent">
              Built for You
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6 }}
            className="mt-6 text-lg leading-relaxed text-slate-400 sm:text-xl"
          >
            From home loans to business financing — get instant decisions, competitive rates, and
            dedicated support at every step of your financial journey.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
            data-highlight-id="landing-hero-ctas"
          >
            <motion.button
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setRegisterOpen(true)}
              className={`${CTA_PRIMARY} w-full px-8 text-base sm:w-auto`}
            >
              Check Eligibility
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.97 }}
              className={`${CTA_SECONDARY} w-full px-8 text-base sm:w-auto`}
            >
              Calculate EMI
            </motion.button>
          </motion.div>

        </div>
      </section>

      {/* ── Stats bar ── */}
      <section className="border-y border-white/5 bg-slate-900/60 py-10">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-8 px-6 sm:grid-cols-4">
          {STATS.map((s, i) => (
            <StatCard key={s.label} {...s} index={i} />
          ))}
        </div>
      </section>

      {/* ── Loan products ── */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-7xl">
          <div className="mb-12 text-center">
            <motion.h2
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
              className="text-3xl font-bold sm:text-4xl"
            >
              Tailored Loan Products
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1, duration: 0.5 }}
              className="mt-3 text-slate-400"
            >
              Choose the loan that matches your needs and goals.
            </motion.p>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
            {LOAN_PRODUCTS.map((p, i) => (
              <LoanCard key={p.id} product={p} index={i} />
            ))}
          </div>
        </div>
      </section>

      {/* ── Features grid ── */}
      <section className="bg-slate-900/50 px-6 py-20">
        <div className="mx-auto max-w-7xl">
          <div className="mb-12 text-center">
            <motion.h2
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
              className="text-3xl font-bold sm:text-4xl"
            >
              Why Choose Mock FinTech?
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1, duration: 0.5 }}
              className="mt-3 text-slate-400"
            >
              We combine technology with personal care to make borrowing easy.
            </motion.p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <FeatureCard key={f.title} {...f} index={i} />
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA banner ── */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-teal-600 to-cyan-700 px-8 py-14 text-center shadow-2xl"
          >
            {/* Background decoration */}
            <div className="pointer-events-none absolute -right-12 -top-12 h-48 w-48 rounded-full bg-white/10" />
            <div className="pointer-events-none absolute -bottom-10 -left-10 h-36 w-36 rounded-full bg-white/10" />

            <h2 className="relative text-3xl font-extrabold text-white sm:text-4xl">
              Ready to Get Started?
            </h2>
            <p className="relative mt-4 text-base text-white/80 sm:text-lg">
              Apply in minutes. Get approved in 48 hours. Our team is ready to help you every step
              of the way.
            </p>

            <div className="relative mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.97 }}
                className={`${CTA_GEOMETRY} min-w-[11rem] bg-white px-8 text-base text-teal-700 shadow-md transition-colors hover:bg-white/90`}
              >
                Apply Now
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.97 }}
                className={`${CTA_GEOMETRY} min-w-[11rem] border border-white/40 px-8 text-base text-white backdrop-blur-sm transition-colors hover:border-white/70 hover:bg-white/10`}
              >
                Speak to an Expert
              </motion.button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-white/5 bg-slate-950 px-6 py-10">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-teal-500 to-cyan-600 text-xs font-bold text-white">
                MFT
              </div>
              <span className="font-semibold text-slate-300">Mock FinTech</span>
            </div>
            <p className="text-xs text-slate-600">
              © {new Date().getFullYear()} Mock FinTech Ltd. Non-RBI Registered NBFC. All rights
              reserved.
            </p>
            <div className="flex gap-6">
              {['Privacy', 'Terms', 'Grievance'].map((l) => (
                <a key={l} href="#" className="text-xs text-slate-500 hover:text-slate-300">
                  {l}
                </a>
              ))}
            </div>
          </div>
        </div>
      </footer>

      {/* ── Floating chat widget ── */}
      <ChatWidget />

      {/* ── Registration dialog ── */}
      <RegisterDialog open={registerOpen} onOpenChange={setRegisterOpen} />

      <LandingAttentionHighlight isOpen={isAttentionOpen} onDismiss={closeAttention} />

      <LandingSpotlightTour
        isOpen={isSpotlightOpen}
        onBack={() => setSpotlightStepIndex((current) => Math.max(0, current - 1))}
        onClose={closeSpotlight}
        onNext={advanceSpotlight}
        stepIndex={spotlightStepIndex}
      />
    </div>
  )
}
