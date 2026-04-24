// src/app/components/admin/AdminLayout.tsx
import { type ReactNode, useEffect, useState } from "react";
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import {
  LayoutDashboard, Database, DollarSign, Activity, MessageSquare,
  Shield as ShieldIcon, Gauge, Cpu, Heart, ChevronLeft, Menu,
  Settings, LogOut, Search, Bell, Tag, Key, Users, UserPlus
} from "lucide-react";
import { AdminProvider, useAdminContext } from "@features/admin/context/AdminContext";
import { AdminAuthProvider, useAdminAuth } from "@features/admin/auth/AdminAuthProvider";
import { MfaPromptProvider } from "@features/admin/auth/MfaPromptProvider";
// `useAdminContext` is kept for the BYOK provider keys (openrouter/nvidia/groq)
// used by the model-config page. The legacy X-Admin-Key field was retired in
// Phase 6g of the admin auth plan.
import { ADMIN_SESSION_EXPIRED_EVENT } from "@/shared/api/http";
import { CommandPalette } from "./CommandPalette";
import { GlobalTraceSheet } from "@features/admin/traces/trace-viewer/GlobalTraceSheet";
import { Popover, PopoverContent, PopoverTrigger } from "@components/ui/popover";
import { KeyInput } from "@components/ui/key-input";
import { ThemeToggle } from "@components/ui/theme-toggle";
import { useLiveGlobalFeed } from "@features/admin/hooks/useLiveGlobalFeed";

type NavItem = {
  path: string;
  label: string;
  icon: typeof LayoutDashboard;
  exact?: boolean;
  superAdminOnly?: boolean;
};

const NAV_ITEMS: readonly NavItem[] = [
  { path: "/admin", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { path: "/admin/knowledge-base", label: "Knowledge Base", icon: Database },
  { path: "/admin/costs", label: "Session Costs", icon: DollarSign },
  { path: "/admin/traces", label: "Chat Traces", icon: Activity },
  { path: "/admin/categories", label: "Question Categories", icon: Tag },
  { path: "/admin/conversations", label: "Conversations", icon: MessageSquare },
  { path: "/admin/guardrails", label: "Guardrails", icon: ShieldIcon },
  { path: "/admin/users", label: "Users & Analytics", icon: Users },
  { path: "/admin/model-config", label: "Models & Router", icon: Cpu },
  { path: "/admin/health", label: "System Health", icon: Heart },
  { path: "/admin/admins", label: "Admin Users", icon: UserPlus, superAdminOnly: true },
];

// KeyInput extracted to @components/ui/key-input

/**
 * Route guard — redirects to `/admin/login` when no JWT session is present.
 *
 * While the session is still hydrating from `GET /admin/auth/me`, render
 * nothing (prevents a flash of unauthorized → redirect).
 *
 * The legacy `X-Admin-Key` fallback branch was removed in Phase 6g of the
 * admin auth plan; the JWT cookie is now the only admin auth path.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const { session, isLoading } = useAdminAuth();

  if (isLoading) return null;
  if (session === null) {
    return <Navigate to="/admin/login" replace />;
  }
  return <>{children}</>;
}

function AdminShell() {
  const [sidebarOpen, setSidebarOpen] = useState(
    () => typeof window !== 'undefined' && window.innerWidth >= 768
  );
  const [cmdOpen, setCmdOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const auth = useAdminContext();
  const { session, logout, refreshSession } = useAdminAuth();

  useLiveGlobalFeed();

  // Listen for 401 events dispatched by http.ts and attempt to re-hydrate
  // the session. If the refresh fails (server confirms the session is gone)
  // the AuthGuard will route to /admin/login on the next render.
  useEffect(() => {
    const handler = () => {
      void refreshSession();
    };
    window.addEventListener(ADMIN_SESSION_EXPIRED_EVENT, handler);
    return () => window.removeEventListener(ADMIN_SESSION_EXPIRED_EVENT, handler);
  }, [refreshSession]);

  // Command Palette Keyboard Shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdOpen((p) => !p);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Auto-close sidebar on route change when on mobile
  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  }, [location.pathname]);

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground font-sans">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-foreground/20 backdrop-blur-[2px] md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar — hairline-bordered, bg-card */}
      <aside className={`
        ${sidebarOpen
          ? "w-64 fixed inset-y-0 left-0 z-40 shadow-2xl md:relative md:shadow-none"
          : "w-0 overflow-hidden md:w-16"
        }
        bg-card border-r border-border flex flex-col shrink-0 transition-[width] duration-200 ease-out
      `}>
        <div className="h-14 flex items-center justify-between px-4 border-b border-border">
          {sidebarOpen && (
            <div className="flex items-center gap-2.5 overflow-hidden">
              {/* Sidebar mark — subtle ring, not a gradient square */}
              <div className="size-7 shrink-0 rounded-md flex items-center justify-center bg-primary/10 text-primary ring-1 ring-primary/20">
                <ShieldIcon className="size-4" />
              </div>
              <span className="text-[15px] font-semibold tracking-tight truncate">MFT Admin</span>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="size-8 shrink-0 rounded-md hover:bg-accent flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
            aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {sidebarOpen ? <ChevronLeft className="size-4" /> : <Menu className="size-4" />}
          </button>
        </div>

        <nav className="flex-1 py-3 px-2 overflow-y-auto space-y-0.5 no-scrollbar">
          {NAV_ITEMS.filter(
            (item) => !item.superAdminOnly || (session?.roles ?? []).includes("super_admin"),
          ).map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              title={!sidebarOpen ? item.label : undefined}
              className={({ isActive }) =>
                `group relative w-full flex items-center gap-3 px-3 py-2 rounded-md text-left text-sm transition-colors ${
                  isActive
                    ? "bg-accent text-foreground font-medium"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {/* Active-state marker: 2px accent bar on the left edge */}
                  {isActive && (
                    <span
                      aria-hidden
                      className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r-full bg-primary"
                    />
                  )}
                  <item.icon className="size-4 shrink-0" />
                  {sidebarOpen && <span className="truncate">{item.label}</span>}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-border p-2 space-y-0.5">
          <button
            onClick={() => setCmdOpen(true)}
            className="w-full flex items-center justify-between px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent/60 hover:text-foreground transition-colors"
          >
            <div className="flex items-center gap-3">
              <Search className="size-4 shrink-0" />
              {sidebarOpen && <span>Search</span>}
            </div>
            {sidebarOpen && (
              <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-tabular bg-secondary rounded text-muted-foreground border border-border">
                ⌘K
              </kbd>
            )}
          </button>
          <button
            onClick={async () => {
              if (session) {
                await logout();
              }
              navigate("/");
            }}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent/60 hover:text-foreground transition-colors"
          >
            <LogOut className="size-4 shrink-0" />
            {sidebarOpen && (
              <span>{session ? "Sign out" : "Exit Admin"}</span>
            )}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="relative flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Signature atmosphere — restrained cyan radial wash, dark-mode dominant */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-[480px]"
          style={{ backgroundImage: "var(--atmosphere-radial-1)" }}
        />

        {/* Top Header */}
        <header className="relative h-14 bg-card/50 backdrop-blur-xl border-b border-border flex items-center justify-between px-4 sm:px-6 shrink-0">
          <div className="flex items-center gap-3">
            {/* Hamburger — always visible when sidebar is closed, especially on mobile */}
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="size-8 shrink-0 rounded-md hover:bg-accent flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors md:hidden"
                aria-label="Open sidebar"
              >
                <Menu className="size-5" />
              </button>
            )}
            <h2 className="text-sm font-medium tracking-tight text-foreground">Production Console</h2>
            <span
              aria-hidden
              className="hidden sm:inline-block text-[10px] font-tabular uppercase tracking-[0.2em] text-muted-foreground border border-border rounded px-1.5 py-0.5"
            >
              v2
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* Keys Popover */}
            <Popover>
              <PopoverTrigger asChild>
                <button className="hidden sm:inline-flex items-center gap-2 px-3 py-1.5 rounded-md border border-border bg-background/50 text-foreground hover:bg-accent transition-colors text-xs font-medium">
                  <Key size={13} className="text-muted-foreground" />
                  <span>Provider Keys</span>
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-80 p-4 space-y-4">
                <div className="space-y-1 mb-2">
                  <h4 className="font-semibold text-sm">Provider Keys</h4>
                  <p className="text-xs text-muted-foreground">BYOK provider keys for session-scoped model execution. Admin auth uses JWT session cookies.</p>
                </div>
                <KeyInput label="OpenRouter Key (Required for OpenRouter sessions)" value={auth.openrouterKey} onChange={auth.setOpenrouterKey} />
                <KeyInput label="NVIDIA Key (Required for NVIDIA sessions)" value={auth.nvidiaKey} onChange={auth.setNvidiaKey} />
                <KeyInput label="Groq Key (Optional)" value={auth.groqKey} onChange={auth.setGroqKey} />
              </PopoverContent>
            </Popover>

            <ThemeToggle />

            <button
              className="relative size-8 rounded-md hover:bg-accent flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Notifications"
            >
              <Bell className="size-4" />
              <span
                aria-hidden
                className="absolute top-1.5 right-1.5 size-1.5 rounded-full bg-destructive ring-2 ring-card"
              />
            </button>

            {/* Super-admin mark — primary-tinted square, not a gradient */}
            <div
              aria-label={session?.sub ?? "admin"}
              className="size-8 rounded-md flex items-center justify-center bg-primary/10 text-primary ring-1 ring-primary/20 text-[11px] font-semibold tracking-wider"
            >
              {(session?.sub ?? "AD").slice(0, 2).toUpperCase()}
            </div>
          </div>
        </header>

        <main className="relative flex-1 overflow-y-auto p-3 sm:p-6">
          <Outlet />
        </main>
      </div>

      <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} />
      <GlobalTraceSheet />
    </div>
  );
}

export function AdminLayout() {
  return (
    <AdminAuthProvider>
      <AdminProvider>
        <AuthGuard>
          <MfaPromptProvider>
            <AdminShell />
          </MfaPromptProvider>
        </AuthGuard>
      </AdminProvider>
    </AdminAuthProvider>
  );
}
