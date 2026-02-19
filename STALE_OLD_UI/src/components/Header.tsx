import { Component, createSignal, onMount, onCleanup, Show } from 'solid-js';
import { Bot, Settings2, LogOut, Network, BarChart3 } from 'lucide-solid';
import { chatActions } from '../stores/chat';
import { sessionState, sessionActions } from '../stores/sessionStore';
import { agentService } from '../services/AgentService';
import SettingsModal, { CONFIG_UPDATED_EVENT } from './SettingsModal';
import ArchitectureModal from './ArchitectureModal';
import type { SessionConfig } from '../types/domain';

const NUDGE_KEY = 'dual_stream_config_nudge_seen';

const Header: Component = () => {
  const [currentModel, setCurrentModel] = createSignal<string>('');
  const [currentProvider, setCurrentProvider] = createSignal<string>('');
  const [showNudge, setShowNudge] = createSignal(false);
  const [isSettingsOpen, setIsSettingsOpen] = createSignal(false);
  const [isArchOpen, setIsArchOpen] = createSignal(false);
  const [isBotHovered, setIsBotHovered] = createSignal(false);

  const isConfigured = () => !!currentModel() && currentModel() !== 'Select Model';

  const updateHeaderLabels = (config?: Partial<SessionConfig>) => {
    if (config?.model_name) {
      setCurrentModel(config.model_name);
      if (config.provider) {
        const p = config.provider;
        setCurrentProvider(p.charAt(0).toUpperCase() + p.slice(1));
      } else {
        setCurrentProvider('');
      }
      const seen = localStorage.getItem(NUDGE_KEY);
      if (seen) setShowNudge(false);
    } else {
      setCurrentModel('Select Model');
      setCurrentProvider('');
      setShowNudge(true);
    }
  };

  onMount(() => {
    // Use sessionState.sessionId
    agentService.getSessionConfig(sessionState.sessionId)
      .then((cfg: SessionConfig) => updateHeaderLabels(cfg))
      .catch(() => updateHeaderLabels({}));

    const onUpdated = (ev: Event) => {
      const detail = (ev as CustomEvent).detail as SessionConfig | undefined;
      updateHeaderLabels(detail);
      if (detail?.model_name) {
        try { localStorage.setItem(NUDGE_KEY, '1'); } catch {}
        setShowNudge(false);
      }
    };
    window.addEventListener(CONFIG_UPDATED_EVENT, onUpdated as EventListener);

    const onReset = () => updateHeaderLabels({});
    window.addEventListener('session-reset', onReset);

    try {
      const seen = localStorage.getItem(NUDGE_KEY);
      if (!seen) setShowNudge(true);
    } catch {
      setShowNudge(true);
    }

    onCleanup(() => {
      window.removeEventListener(CONFIG_UPDATED_EVENT, onUpdated as EventListener);
      window.removeEventListener('session-reset', onReset);
    });
  });

  const handleLogout = async () => {
    if (confirm('Are you sure you want to end this session? History will be cleared.')) {
      await agentService.logout(sessionState.sessionId);
      sessionActions.resetSession();
      chatActions.reset();
    }
  };

  return (
    <>
      <header class="flex shrink-0 items-center justify-between border-b border-slate-200 bg-white/80 px-4 lg:px-6 py-3 backdrop-blur-md dark:border-slate-800 dark:bg-slate-900/80 z-10 sticky top-0 transition-all duration-300">
        <div class="flex items-center gap-3 group cursor-default" onMouseEnter={() => setIsBotHovered(true)} onMouseLeave={() => setIsBotHovered(false)}>
          <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-linear-to-br from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/20 transition-transform group-hover:scale-110 group-hover:rotate-3">
            <Bot size={20} class={isBotHovered() ? 'animate-bounce' : ''} />
          </div>
          <div>
            <h1 class="text-sm font-bold tracking-tight text-slate-900 dark:text-slate-100 transition-colors group-hover:text-indigo-600 dark:group-hover:text-indigo-400">
              Dual-Stream AI
            </h1>
            <div class="flex items-center gap-1.5 text-[10px] font-medium text-slate-500 dark:text-slate-400">
              <span class={`h-1.5 w-1.5 rounded-full animate-pulse ${isConfigured() ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
              <span class={`opacity-75 ${!isConfigured() ? 'text-amber-600 dark:text-amber-400 font-bold' : ''}`}>
                {currentProvider() ? `${currentProvider()} • ` : ''}{currentModel()}
              </span>
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <a href="/dashboard" class="hidden sm:flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-indigo-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300 dark:hover:bg-slate-900 transition-all shadow-sm">
            <BarChart3 size={16} /> <span>Dashboard</span>
          </a>
          <button onClick={() => setIsArchOpen(true)} class="hidden sm:flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-indigo-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300 dark:hover:bg-slate-900 transition-all shadow-sm">
            <Network size={16} /> <span>Architecture</span>
          </button>
          <button onClick={() => setIsSettingsOpen(true)} class="flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-all shadow-sm border-slate-200 bg-white text-slate-700 hover:bg-slate-50 hover:text-indigo-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
            <Settings2 size={16} /> <span class="hidden sm:inline">Configure</span>
          </button>
          <Show when={showNudge()}>
             <div class="absolute right-16 top-14 z-50 w-48 animate-bounce rounded-xl bg-indigo-600 p-3 text-center text-[11px] font-bold text-white shadow-xl pointer-events-none">
               <div class="absolute -top-1 right-6 h-3 w-3 rotate-45 bg-indigo-600"></div>
               {isConfigured() ? 'Configure your model here! 👆' : '⚠️ Configure to start! 👆'}
             </div>
          </Show>
          <button onClick={handleLogout} class="flex items-center gap-2 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-100 dark:border-red-900/30 dark:bg-red-900/10 dark:text-red-400 dark:hover:bg-red-900/20 transition-all">
            <LogOut size={16} /> <span class="hidden sm:inline">End</span>
          </button>
        </div>
      </header>

      <Show when={isSettingsOpen()}>
        <SettingsModal isOpen={isSettingsOpen()} onClose={() => setIsSettingsOpen(false)} />
      </Show>
      <Show when={isArchOpen()}>
        <ArchitectureModal isOpen={isArchOpen()} onClose={() => setIsArchOpen(false)} />
      </Show>
    </>
  );
};

export default Header;
