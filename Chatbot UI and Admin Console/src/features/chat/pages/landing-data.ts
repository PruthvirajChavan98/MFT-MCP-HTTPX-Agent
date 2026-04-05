// ─── Landing page static data ─────────────────────────────────────────────────

export const LOAN_PRODUCTS = [
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

export const FEATURES = [
  {
    icon: '⚡',
    title: 'Instant Eligibility Check',
    desc: 'Get your loan eligibility in under 60 seconds with our AI-powered assessment engine.',
  },
  {
    icon: '🔒',
    title: 'Bank-Grade Security',
    desc: '256-bit encryption and Non-RBI-compliant data handling keeps your information safe.',
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

export const STATS = [
  { value: '₹50,000 Cr+', label: 'Loans Disbursed' },
  { value: '5 Lakh+', label: 'Happy Customers' },
  { value: '48 hrs', label: 'Avg Approval Time' },
  { value: '99.2%', label: 'Customer Satisfaction' },
]

export const LANDING_SPOTLIGHT_STORAGE_KEY = 'mft_landing_spotlight_dismissed_v1'

export const LANDING_SPOTLIGHT_STEPS = [
  {
    targetId: 'landing-nav-ctas',
    title: 'Start with the main actions',
    description:
      'This rail keeps the key flows close by: admin access, quick registration, and a direct route to apply.',
  },
  {
    targetId: 'landing-chat-launcher',
    title: 'Need help instantly?',
    description:
      'Open the assistant at any time to ask about rates, eligibility, repayment plans, or your application.',
  },
] as const
