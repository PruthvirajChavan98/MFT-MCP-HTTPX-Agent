import { type Component, createSignal, onMount, onCleanup, Show, createMemo } from 'solid-js';
import ChatInterface from './components/ChatInterface';
import DashboardPage from './pages/DashboardPage';
import FaqToolkitPage from './pages/FaqToolkitPage';
import ResponsiveShell from './components/layout/ResponsiveShell';

const App: Component = () => {
  const [currentPath, setCurrentPath] = createSignal(window.location.pathname);

  onMount(() => {
    const handlePopState = () => setCurrentPath(window.location.pathname);
    window.addEventListener('popstate', handlePopState);

    window.addEventListener('navigate', ((e: CustomEvent) => {
      const path = e.detail;
      window.history.pushState({}, '', path);
      setCurrentPath(path);
    }) as EventListener);

    onCleanup(() => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('navigate', ((e: CustomEvent) => {}) as EventListener);
    });
  });

  // ✅ FIX: Robust matching ignores trailing slash
  const route = createMemo(() => {
    const p = currentPath().toLowerCase();
    return p.endsWith('/') && p.length > 1 ? p.slice(0, -1) : p;
  });

  return (
    <ResponsiveShell>
      <Show when={route() === '/dashboard'}>
        <DashboardPage />
      </Show>

      <Show when={route() === '/faqs-toolkit'}>
        <FaqToolkitPage />
      </Show>

      {/* Explicit check ensures chat only renders when NOT on other pages */}
      <Show when={route() !== '/dashboard' && route() !== '/faqs-toolkit'}>
        <ChatInterface />
      </Show>
    </ResponsiveShell>
  );
};

export default App;
