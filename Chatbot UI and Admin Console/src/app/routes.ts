import { createElement, lazy } from 'react'
import { createBrowserRouter } from 'react-router'
import { RouteErrorBoundary } from './components/RouteErrorBoundary'

const LandingPage = lazy(async () => {
  const module = await import('./components/LandingPage')
  return { default: module.LandingPage }
})
const AdminLayout = lazy(async () => {
  const module = await import('./components/admin/AdminLayout')
  return { default: module.AdminLayout }
})
const Dashboard = lazy(async () => {
  const module = await import('./components/admin/Dashboard')
  return { default: module.Dashboard }
})
const KnowledgeBase = lazy(async () => {
  const module = await import('./components/admin/KnowledgeBase')
  return { default: module.KnowledgeBase }
})
const ChatCosts = lazy(async () => {
  const module = await import('./components/admin/ChatCosts')
  return { default: module.ChatCosts }
})
const ChatTraces = lazy(async () => {
  const module = await import('./components/admin/ChatTraces')
  return { default: module.ChatTraces }
})
const QuestionCategories = lazy(async () => {
  const module = await import('./components/admin/QuestionCategories')
  return { default: module.QuestionCategories }
})
const Conversations = lazy(async () => {
  const module = await import('./components/admin/Conversations')
  return { default: module.Conversations }
})
const ModelConfig = lazy(async () => {
  const module = await import('./components/admin/ModelConfig')
  return { default: module.ModelConfig }
})
const Guardrails = lazy(async () => {
  const module = await import('./components/admin/Guardrails')
  return { default: module.Guardrails }
})
const UsersAnalytics = lazy(async () => {
  const module = await import('./components/admin/UsersAnalytics')
  return { default: module.UsersAnalytics }
})
const Feedback = lazy(async () => {
  const module = await import('./components/admin/Feedback')
  return { default: module.Feedback }
})
const SystemHealth = lazy(async () => {
  const module = await import('./components/admin/SystemHealth')
  return { default: module.SystemHealth }
})

export const router = createBrowserRouter([
  {
    path: '/',
    Component: LandingPage,
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
