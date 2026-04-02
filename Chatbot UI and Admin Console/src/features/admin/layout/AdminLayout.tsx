// src/app/components/admin/AdminLayout.tsx
import { useState, useEffect } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import {
  LayoutDashboard, Database, DollarSign, Activity, MessageSquare,
  Shield as ShieldIcon, Gauge, Cpu, Heart, ChevronLeft, Menu,
  Settings, LogOut, Search, Bell, Tag, Key, Eye, EyeOff, AlertCircle, Users
} from "lucide-react";
import { AdminProvider, useAdminContext } from "@features/admin/context/AdminContext";
import { CommandPalette } from "./CommandPalette";
import { GlobalTraceSheet } from "@features/admin/traces/trace-viewer/GlobalTraceSheet";
import { Popover, PopoverContent, PopoverTrigger } from "@components/ui/popover";
import { Input } from "@components/ui/input";
import { Label } from "@components/ui/label";
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

function KeyInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-semibold text-slate-600">{label}</Label>
      <div className="relative">
        <Input
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={`Enter ${label}...`}
          className="pr-8 text-xs font-mono"
        />
        <button
          type="button"
          onClick={() => setVisible((p) => !p)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
        >
          {visible ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>
    </div>
  );
}

function AdminShell() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [cmdOpen, setCmdOpen] = useState(false);
  const navigate = useNavigate();
  const auth = useAdminContext();

  useLiveGlobalFeed(auth.adminKey);

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

  const missingAdminKey = !auth.adminKey.trim();

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className={`${sidebarOpen ? "w-64" : "w-16"} bg-white border-r border-gray-200 flex flex-col shrink-0 transition-all duration-300 ease-in-out`}>
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
          <button onClick={() => navigate("/")} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-all">
            <LogOut className="w-4 h-4 shrink-0" />
            {sidebarOpen && <span className="text-sm font-medium">Exit Admin</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-slate-800">Production Console</h2>
          </div>

          <div className="flex items-center gap-4">
            {/* Keys Popover */}
            <Popover>
              <PopoverTrigger asChild>
                <button className={`flex items-center gap-2 px-3 py-1.5 rounded-md border transition-all text-xs font-semibold ${missingAdminKey ? 'border-red-200 bg-red-50 text-red-600 hover:bg-red-100' : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'}`}>
                  <Key size={14} />
                  <span>API Keys</span>
                  {missingAdminKey && <span className="relative flex h-2 w-2"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span></span>}
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-80 p-4 space-y-4 shadow-xl">
                <div className="space-y-1 mb-2">
                  <h4 className="font-semibold text-sm text-slate-900">Authentication</h4>
                  <p className="text-xs text-slate-500">Required headers for accessing production backend endpoints.</p>
                </div>
                {missingAdminKey && (
                  <div className="flex items-start gap-2 p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-xs">
                    <AlertCircle size={14} className="shrink-0 mt-0.5" />
                    <p>Admin API key is required for admin analytics endpoints. Provider keys are only required for model-dependent actions.</p>
                  </div>
                )}
                <KeyInput label="Admin API Key (X-Admin-Key)" value={auth.adminKey} onChange={auth.setAdminKey} />
                <KeyInput label="OpenRouter Key (X-OpenRouter-Key)" value={auth.openrouterKey} onChange={auth.setOpenrouterKey} />
                <KeyInput label="Groq Key (X-Groq-Key)" value={auth.groqKey} onChange={auth.setGroqKey} />
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

        <main className="flex-1 overflow-y-auto p-6 bg-slate-50/50">
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
    <AdminProvider>
      <AdminShell />
    </AdminProvider>
  );
}
