// src/app/components/admin/AdminLayout.tsx
import { type ReactNode, useEffect, useState } from "react";
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import {
  LayoutDashboard, Database, DollarSign, Activity, MessageSquare,
  Shield as ShieldIcon, Gauge, Cpu, Heart, ChevronLeft, Menu,
  Settings, LogOut, Search, Bell, Tag, Key, Users
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
import { useLiveGlobalFeed } from "@features/admin/hooks/useLiveGlobalFeed";

const NAV_ITEMS = [
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
    <div className="flex h-screen bg-gray-50 overflow-hidden font-sans">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        ${sidebarOpen
          ? "w-64 fixed inset-y-0 left-0 z-40 shadow-xl md:relative md:shadow-none"
          : "w-0 overflow-hidden md:w-16"
        }
        bg-white border-r border-gray-200 flex flex-col shrink-0 transition-all duration-300 ease-in-out
      `}>
        <div className="h-14 flex items-center justify-between px-4 border-b border-gray-100">
          {sidebarOpen && (
            <div className="flex items-center gap-2 overflow-hidden">
              <div className="w-7 h-7 shrink-0 rounded-lg flex items-center justify-center bg-linear-to-r from-cyan-500 to-teal-500">
                <ShieldIcon className="w-4 h-4 text-white" />
              </div>
              <span className="font-bold text-slate-900 truncate" style={{ fontSize: 15 }}>MFT Admin</span>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="w-8 h-8 shrink-0 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-500 transition-colors"
          >
            {sidebarOpen ? <ChevronLeft className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </div>

        <nav className="flex-1 py-3 px-2 overflow-y-auto space-y-1 no-scrollbar">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              title={!sidebarOpen ? item.label : undefined}
              className={({ isActive }) => `w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left ${isActive ? "text-white shadow-md bg-linear-to-r from-cyan-500 to-teal-500" : "text-gray-600 hover:bg-gray-100"
                }`}
            >
              <item.icon className="w-4 h-4 shrink-0" />
              {sidebarOpen && <span className="text-sm font-medium truncate">{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-gray-100 p-2 space-y-1">
          <button onClick={() => setCmdOpen(true)} className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-all">
            <div className="flex items-center gap-3">
              <Search className="w-4 h-4 shrink-0" />
              {sidebarOpen && <span className="text-sm font-medium">Search</span>}
            </div>
            {sidebarOpen && <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-mono bg-gray-200 rounded text-gray-500">⌘K</kbd>}
          </button>
          <button
            onClick={async () => {
              if (session) {
                await logout();
              }
              navigate("/");
            }}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-all"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            {sidebarOpen && (
              <span className="text-sm font-medium">
                {session ? "Sign out" : "Exit Admin"}
              </span>
            )}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 sm:px-6 shrink-0">
          <div className="flex items-center gap-3">
            {/* Hamburger — always visible when sidebar is closed, especially on mobile */}
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="w-8 h-8 shrink-0 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-500 transition-colors md:hidden"
              >
                <Menu className="w-5 h-5" />
              </button>
            )}
            <h2 className="text-sm font-semibold text-slate-800">Production Console</h2>
          </div>

          <div className="flex items-center gap-4">
            {/* Keys Popover */}
            <Popover>
              <PopoverTrigger asChild>
                <button className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 transition-all text-xs font-semibold">
                  <Key size={14} />
                  <span className="hidden sm:inline">Provider Keys</span>
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-80 p-4 space-y-4 shadow-xl">
                <div className="space-y-1 mb-2">
                  <h4 className="font-semibold text-sm text-slate-900">Provider Keys</h4>
                  <p className="text-xs text-slate-500">BYOK provider keys for session-scoped model execution. Admin auth now uses JWT session cookies.</p>
                </div>
                <KeyInput label="OpenRouter Key (Required for OpenRouter sessions)" value={auth.openrouterKey} onChange={auth.setOpenrouterKey} />
                <KeyInput label="NVIDIA Key (Required for NVIDIA sessions)" value={auth.nvidiaKey} onChange={auth.setNvidiaKey} />
                <KeyInput label="Groq Key (Optional)" value={auth.groqKey} onChange={auth.setGroqKey} />
              </PopoverContent>
            </Popover>

            <button className="w-8 h-8 rounded-full hover:bg-gray-100 flex items-center justify-center text-gray-500 relative transition-colors">
              <Bell className="w-4 h-4" />
              <span className="absolute top-2 right-2 w-1.5 h-1.5 bg-red-500 rounded-full border border-white" />
            </button>
            <div className="w-8 h-8 rounded-full flex items-center justify-center text-white shadow-sm" style={{ background: "linear-gradient(135deg, #14b8a6 0%, #0d9488 100%)", fontSize: 11, fontWeight: 700 }}>
              AD
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-3 sm:p-6 bg-slate-50/50">
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
