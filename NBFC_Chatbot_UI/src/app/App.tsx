import { Route, Router } from '@solidjs/router'
import AdminLayout from '../pages/admin/AdminLayout'
import CategoriesPage from '../pages/admin/CategoriesPage'
import ConversationsPage from '../pages/admin/ConversationsPage'
import CostsPage from '../pages/admin/CostsPage'
import DashboardPage from '../pages/admin/DashboardPage'
import FeedbackPage from '../pages/admin/FeedbackPage'
import GuardrailsPage from '../pages/admin/GuardrailsPage'
import KnowledgeBasePage from '../pages/admin/KnowledgeBasePage'
import ModelConfigPage from '../pages/admin/ModelConfigPage'
import TracesPage from '../pages/admin/TracesPage'
import UsersPage from '../pages/admin/UsersPage'
import ChatPage from '../pages/chat/ChatPage'

export default function App() {
  return (
    <Router>
      <Route path="/" component={ChatPage} />

      <Route path="/admin" component={AdminLayout}>
        <Route path="/" component={DashboardPage} />
        <Route path="/knowledge-base" component={KnowledgeBasePage} />
        <Route path="/costs" component={CostsPage} />
        <Route path="/traces" component={TracesPage} />
        <Route path="/categories" component={CategoriesPage} />
        <Route path="/conversations" component={ConversationsPage} />
        <Route path="/model-config" component={ModelConfigPage} />
        <Route path="/guardrails" component={GuardrailsPage} />
        <Route path="/users" component={UsersPage} />
        <Route path="/feedback" component={FeedbackPage} />
      </Route>
    </Router>
  )
}
