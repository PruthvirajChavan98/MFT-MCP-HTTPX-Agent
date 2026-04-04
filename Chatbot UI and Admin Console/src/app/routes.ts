import { createElement, lazy } from 'react'
import { createBrowserRouter } from 'react-router'
import { RouteErrorBoundary } from '@components/RouteErrorBoundary'

const LandingPage = lazy(async () => {
  const module = await import('@features/chat/pages/NBFCLandingPage')
  return { default: module.NBFCLandingPage }
})
const AdminLayout = lazy(async () => {
  const module = await import('@features/admin/layout/AdminLayout')
  return { default: module.AdminLayout }
})
const Dashboard = lazy(async () => {
  const module = await import('@features/admin/pages/Dashboard')
  return { default: module.Dashboard }
})
const KnowledgeBase = lazy(async () => {
  const module = await import('@features/admin/knowledge-base/KnowledgeBasePage')
  return { default: module.KnowledgeBasePage }
})
const ChatCosts = lazy(async () => {
  const module = await import('@features/admin/costs/ChatCostsPage')
  return { default: module.ChatCostsPage }
})
const ChatTraces = lazy(async () => {
  const module = await import('@features/admin/traces/ChatTracesPage')
  return { default: module.ChatTracesPage }
})
const QuestionCategories = lazy(async () => {
  const module = await import('@features/admin/pages/QuestionCategories')
  return { default: module.QuestionCategories }
})
const Conversations = lazy(async () => {
  const module = await import('@features/admin/pages/Conversations')
  return { default: module.Conversations }
})
const ModelConfig = lazy(async () => {
  const module = await import('@features/admin/pages/ModelConfig')
  return { default: module.ModelConfig }
})
const Guardrails = lazy(async () => {
  const module = await import('@features/admin/guardrails/GuardrailsPage')
  return { default: module.GuardrailsPage }
})
const UsersAnalytics = lazy(async () => {
  const module = await import('@features/admin/pages/UsersAnalytics')
  return { default: module.UsersAnalytics }
})
const Feedback = lazy(async () => {
  const module = await import('@features/admin/pages/Feedback')
  return { default: module.Feedback }
})
const SystemHealth = lazy(async () => {
  const module = await import('@features/admin/pages/SystemHealth')
  return { default: module.SystemHealth }
})
const ArchitecturePage = lazy(async () => {
  const module = await import('@features/chat/pages/ArchitecturePage')
  return { default: module.ArchitecturePage }
})

export const router = createBrowserRouter([
  {
    path: '/',
    Component: LandingPage,
    errorElement: createElement(RouteErrorBoundary),
  },
  {
    path: '/architecture',
    Component: ArchitecturePage,
    errorElement: createElement(RouteErrorBoundary),
  },
  {
    path: '/admin',
    Component: AdminLayout,
    errorElement: createElement(RouteErrorBoundary),
    children: [
      { index: true, Component: Dashboard },
      { path: 'knowledge-base', Component: KnowledgeBase },
      { path: 'costs', Component: ChatCosts },
      { path: 'traces', Component: ChatTraces },
      { path: 'categories', Component: QuestionCategories },
      { path: 'conversations', Component: Conversations },
      { path: 'model-config', Component: ModelConfig },
      { path: 'guardrails', Component: Guardrails },
      { path: 'users', Component: UsersAnalytics },
      { path: 'feedback', Component: Feedback },
      { path: 'health', Component: SystemHealth },
    ],
  },
])
