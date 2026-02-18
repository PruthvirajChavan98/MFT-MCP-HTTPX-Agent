import { Route, Router } from '@solidjs/router'
import { AppShell } from '../components/layout/AppShell'
import { AdminPage } from '../pages/AdminPage'
import { HomePage } from '../pages/HomePage'
import { OperationsPage } from '../pages/OperationsPage'
import { StreamsPage } from '../pages/StreamsPage'
import { WorkbenchPage } from '../pages/WorkbenchPage'

function NotFoundPage() {
  return (
    <section class="card">
      <h2>Page Not Found</h2>
      <p>The route you requested does not exist in this frontend application.</p>
    </section>
  )
}

export function App() {
  return (
    <Router root={AppShell}>
      <Route path="/" component={HomePage} />
      <Route path="/workbench" component={WorkbenchPage} />
      <Route path="/operations" component={OperationsPage} />
      <Route path="/streams" component={StreamsPage} />
      <Route path="/admin" component={AdminPage} />
      <Route path="*404" component={NotFoundPage} />
    </Router>
  )
}
