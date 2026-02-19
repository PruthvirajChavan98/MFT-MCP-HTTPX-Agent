import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router";
import {
  LayoutDashboard, Database, DollarSign, Activity, MessageSquare,
  Shield as ShieldIcon, Gauge, Cpu, Heart, ChevronLeft, Menu,
  Settings, LogOut, Search, Bell, Tag
} from "lucide-react";

const NAV_ITEMS = [
  { path: "/admin", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { path: "/admin/knowledge-base", label: "Knowledge Base", icon: Database },
  { path: "/admin/session-costs", label: "Session Costs", icon: DollarSign },
  { path: "/admin/traces", label: "Chat Traces", icon: Activity },
  { path: "/admin/categories", label: "Question Categories", icon: Tag },
  { path: "/admin/feedback", label: "Feedback", icon: MessageSquare },
  { path: "/admin/guardrails", label: "Guardrails", icon: ShieldIcon },
  { path: "/admin/rate-limiting", label: "Rate Limiting", icon: Gauge },
  { path: "/admin/models", label: "Models & Router", icon: Cpu },
  { path: "/admin/health", label: "System Health", icon: Heart },
];

export function AdminLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path: string, exact?: boolean) => {
    if (exact) return location.pathname === path;
    return location.pathname.startsWith(path);
  };

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? "w-64" : "w-16"
        } bg-white border-r border-gray-200 flex flex-col shrink-0 transition-all duration-200`}
      >
        {/* Logo */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-gray-100">
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center"
                style={{ background: "var(--brand-gradient)" }}
              >
                <ShieldIcon className="w-4 h-4 text-white" />
              </div>
              <span style={{ fontWeight: 700, fontSize: 15 }}>HFCL Admin</span>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-500"
          >
            {sidebarOpen ? <ChevronLeft className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </div>

        {/* Nav Items */}
        <nav className="flex-1 py-3 px-2 overflow-y-auto space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = isActive(item.path, item.exact);
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-all text-left ${
                  active
                    ? "text-white"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
                style={active ? { background: "var(--brand-gradient)" } : {}}
                title={!sidebarOpen ? item.label : undefined}
              >
                <item.icon className="w-4 h-4 shrink-0" />
                {sidebarOpen && <span style={{ fontSize: 14 }}>{item.label}</span>}
              </button>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="border-t border-gray-100 p-2 space-y-0.5">
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-all">
            <Settings className="w-4 h-4 shrink-0" />
            {sidebarOpen && <span style={{ fontSize: 14 }}>Settings</span>}
          </button>
          <button
            onClick={() => navigate("/")}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-all"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            {sidebarOpen && <span style={{ fontSize: 14 }}>Back to Site</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search..."
                className="pl-9 pr-4 py-1.5 bg-gray-50 border border-gray-200 rounded-lg w-64 outline-none focus:border-brand-main transition-colors"
                style={{ fontSize: 13 }}
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-500 relative">
              <Bell className="w-4 h-4" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
            </button>
            <div className="w-8 h-8 rounded-full flex items-center justify-center text-white" style={{ background: "var(--brand-gradient)", fontSize: 12, fontWeight: 600 }}>
              AD
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
