import { AdminAuthProvider } from './AdminAuthProvider'
import { LoginPage } from './LoginPage'

/**
 * Top-level route wrapper for the admin login page.
 *
 * Provides its own AdminAuthProvider so the login page can call
 * `useAdminAuth().login(...)` without depending on AdminLayout's provider
 * (which is gated behind the auth check). After successful login, the
 * navigate('/admin') call unmounts this tree and remounts AdminLayout's
 * tree, which re-hydrates from the cookie that login just set.
 */
export function AdminLoginRoute() {
  return (
    <AdminAuthProvider>
      <LoginPage />
    </AdminAuthProvider>
  )
}
