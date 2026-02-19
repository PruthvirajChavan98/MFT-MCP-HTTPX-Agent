import { createBrowserRouter } from 'react-router'
import { LandingPage } from './components/LandingPage'
import { AdminLayout } from './components/admin/AdminLayout'
import { Dashboard } from './components/admin/Dashboard'
import { KnowledgeBase } from './components/admin/KnowledgeBase'
import { ChatCosts } from './components/admin/ChatCosts'
import { ChatTraces } from './components/admin/ChatTraces'
import { QuestionCategories } from './components/admin/QuestionCategories'
import { Conversations } from './components/admin/Conversations'
import { ModelConfig } from './components/admin/ModelConfig'
import { Guardrails } from './components/admin/Guardrails'
import { UsersAnalytics } from './components/admin/UsersAnalytics'
import { Feedback } from './components/admin/Feedback'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: LandingPage,
  },
  {
    path: '/admin',
    Component: AdminLayout,
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
    ],
  },
])
