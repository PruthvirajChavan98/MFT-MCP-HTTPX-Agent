import { motion, useInView } from 'motion/react'
import { useRef } from 'react'
import { Link } from 'react-router'
import { ChatWidget } from '../components/ChatWidget'

// ─── Loan product data ────────────────────────────────────────────────────────

const LOAN_PRODUCTS = [
  {
    id: 'home',
    icon: '🏠',
    title: 'Home Loans',
    subtitle: 'Build your dream home',
    rate: '8.50%',
    rateLabel: 'p.a. onwards',
    features: ['Up to ₹5 Crore', 'Tenure up to 30 years', 'Quick approval in 48 hrs'],
    accent: 'from-teal-500 to-cyan-600',
    border: 'hover:border-teal-400',
    badge: 'Most Popular',
  },
  {
    id: 'business',
    icon: '🏢',
    title: 'Business Loans',
    subtitle: 'Fuel your growth',
    rate: '14.00%',
    rateLabel: 'p.a. onwards',
    features: ['Up to ₹2 Crore', 'No collateral required', 'Flexible repayment'],
    accent: 'from-violet-500 to-purple-600',
    border: 'hover:border-violet-400',
    badge: null,
  },
  {
    id: 'personal',
    icon: '💼',
    title: 'Personal Loans',
    subtitle: 'Meet life\'s milestones',
    rate: '12.50%',
    rateLabel: 'p.a. onwards',
    features: ['Up to ₹50 Lakh', 'Instant disbursal', 'Minimal documentation'],
    accent: 'from-orange-500 to-amber-600',
    border: 'hover:border-orange-400',
    badge: null,
  },
  {
    id: 'vehicle',
    icon: '🚗',
    title: 'Vehicle Loans',
    subtitle: 'Drive your ambitions',
    rate: '9.75%',
    rateLabel: 'p.a. onwards',
    features: ['New & used vehicles', 'Up to 95% LTV', 'Doorstep service'],
    accent: 'from-sky-500 to-blue-600',
    border: 'hover:border-sky-400',
    badge: null,
  },
] as const

const FEATURES = [
  {
    icon: '⚡',
    title: 'Instant Eligibility Check',
    desc: 'Get your loan eligibility in under 60 seconds with our AI-powered assessment engine.',
  },
  {
    icon: '🔒',
    title: 'Bank-Grade Security',
    desc: '256-bit encryption and RBI-compliant data handling keeps your information safe.',
  },
  {
    icon: '📱',
    title: '100% Digital Process',
    desc: 'Apply, track, and manage your loan entirely online — no branch visits needed.',
  },
  {
    icon: '🤝',
    title: 'Dedicated Relationship Manager',
    desc: 'Get a personal RM assigned to guide you through every step of your loan journey.',
  },
  {
    icon: '💰',
    title: 'Best-in-Class Rates',
    desc: 'Competitive interest rates with transparent fee structures and no hidden charges.',
  },
  {
    icon: '🤖',
    title: 'AI-Powered Support',
    desc: '24×7 intelligent chatbot answers all your queries in real-time with instant accuracy.',
  },
]

const STATS = [
  { value: '₹50,000 Cr+', label: 'Loans Disbursed' },
  { value: '5 Lakh+', label: 'Happy Customers' },
  { value: '48 hrs', label: 'Avg Approval Time' },
  { value: '99.2%', label: 'Customer Satisfaction' },
]

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

// ─── Main component ────────────────────────────────────────────────────────────

export function NBFCLandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* ── Nav ── */}
      <nav className="sticky top-0 z-40 border-b border-white/5 bg-slate-950/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-teal-500 to-cyan-600 font-bold text-white text-sm shadow">
              MFT
            </div>
            <span className="text-lg font-bold tracking-tight">Mock FinTech</span>
          </div>

          <div className="hidden items-center gap-8 md:flex">
            {['Home Loans', 'Business Loans', 'Personal Loans', 'Rates'].map((item) => (
              <a key={item} href="#" className="text-sm text-slate-400 transition-colors hover:text-white">
                {item}
              </a>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/admin"
              className="hidden rounded-lg px-4 py-2 text-sm text-slate-400 transition-colors hover:text-white md:inline-flex"
            >
              Admin
            </Link>
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              className="rounded-lg bg-gradient-to-r from-teal-500 to-cyan-600 px-4 py-2 text-sm font-semibold text-white shadow transition-opacity hover:opacity-90"
            >
              Apply Now
            </motion.button>
          </div>
        </div>
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
            RBI Registered NBFC • Trusted Since 2005
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
          >
            <motion.button
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.97 }}
              className="w-full rounded-xl bg-gradient-to-r from-teal-500 to-cyan-600 px-8 py-3.5 text-base font-semibold text-white shadow-lg transition-opacity hover:opacity-90 sm:w-auto"
            >
              Check Eligibility
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.97 }}
              className="w-full rounded-xl border border-white/15 bg-white/5 px-8 py-3.5 text-base font-semibold text-white backdrop-blur-sm transition-colors hover:bg-white/10 sm:w-auto"
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
                className="rounded-xl bg-white px-8 py-3 font-semibold text-teal-700 shadow-md transition-colors hover:bg-white/90"
              >
                Apply Now
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.97 }}
                className="rounded-xl border-2 border-white/40 px-8 py-3 font-semibold text-white backdrop-blur-sm transition-colors hover:border-white/70"
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
              © {new Date().getFullYear()} Mock FinTech Ltd. RBI Registered NBFC. All rights
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
    </div>
  )
}
