import { Component, createEffect, createMemo, createSignal, Show, onCleanup } from 'solid-js';
import { ChevronDown, BrainCircuit, Maximize2, X, Copy } from 'lucide-solid';
import clsx from 'clsx';
import MarkdownIt from 'markdown-it';

const md = new MarkdownIt({
  html: true, // ✅ FIX: Allow HTML tags (<span>) for color coding
  linkify: true,
  breaks: true,
});

const formatReasoning = (text: string) => {
  if (!text) return '';
  // Basic cleanup but PRESERVE SPACES
  let clean = text.replace(/\\n/g, '\n').replace(/\\"/g, '"');
  return clean;
};

interface ReasoningAccordionProps {
  reasoning: string;
  isStreaming: boolean;
}

const ReasoningAccordion: Component<ReasoningAccordionProps> = (props) => {
  const [isOpen, setIsOpen] = createSignal(false);
  const [isFullOpen, setIsFullOpen] = createSignal(false);
  const [copied, setCopied] = createSignal(false);

  const shouldRender = createMemo(() => isOpen() || isFullOpen());

  const htmlContent = createMemo(() => {
    if (!shouldRender()) return '';
    return md.render(formatReasoning(props.reasoning));
  });

  const closeFull = () => { setIsFullOpen(false); setCopied(false); };

  const copyAll = async () => {
    try {
      await navigator.clipboard.writeText(props.reasoning || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 900);
    } catch {}
  };

  createEffect(() => {
    if (!isFullOpen()) return;
    const onKeyDown = (e: KeyboardEvent) => { if (e.key === 'Escape') closeFull(); };
    window.addEventListener('keydown', onKeyDown);
    onCleanup(() => window.removeEventListener('keydown', onKeyDown));
  });

  return (
    <div class="border-l-2 border-slate-200 pl-4 my-2 dark:border-slate-800">
      <div class="flex items-center justify-between gap-2">
        <button
          onClick={() => setIsOpen(!isOpen())}
          class="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
        >
          <div class={clsx('transition-transform duration-200', isOpen() ? 'rotate-0' : '-rotate-90')}>
            <ChevronDown size={16} />
          </div>
          <BrainCircuit size={16} />
          <span>Thought Process</span>
          <Show when={props.isStreaming}>
            <span class="inline-block h-2 w-2 animate-pulse rounded-full bg-blue-500 ml-2"></span>
          </Show>
        </button>

        <div class="flex items-center gap-2">
          <button type="button" onClick={copyAll} class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 transition-colors">
            <Copy size={14} /> <span class="hidden sm:inline">{copied() ? 'Copied' : 'Copy'}</span>
          </button>
          <button type="button" onClick={() => setIsFullOpen(true)} class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 transition-colors">
            <Maximize2 size={14} /> <span class="hidden sm:inline">Full</span>
          </button>
        </div>
      </div>

      <div class={clsx('grid transition-all duration-300 ease-in-out', isOpen() ? 'grid-rows-[1fr] opacity-100 mt-2' : 'grid-rows-[0fr] opacity-0 mt-0')}>
        <div class="overflow-hidden">
          <div
            class="markdown-content font-mono text-xs bg-slate-50 dark:bg-slate-900/30 p-3 rounded-md text-slate-600 dark:text-slate-400 whitespace-pre-wrap leading-relaxed"
            innerHTML={htmlContent()}
          />
        </div>
      </div>

      <Show when={isFullOpen()}>
        <div class="fixed inset-0 z-9999 bg-black/60 backdrop-blur-sm" onClick={(e) => e.target === e.currentTarget && closeFull()}>
          <div class="absolute inset-0 flex items-center justify-center p-3 sm:p-6">
            <div class="w-full max-w-5xl h-[85vh] rounded-2xl border border-slate-700/60 bg-slate-950/85 shadow-2xl overflow-hidden flex flex-col">
              <div class="flex items-center justify-between px-4 py-3 border-b border-slate-800/70 shrink-0">
                <div class="flex items-center gap-2 text-slate-200">
                  <BrainCircuit size={16} />
                  <span class="text-sm font-semibold">Full Thought Process</span>
                </div>
                <button type="button" onClick={closeFull} class="text-slate-400 hover:text-white"><X size={20} /></button>
              </div>
              <div class="flex-1 overflow-y-auto p-6">
                <div
                  class="markdown-content font-mono text-sm text-slate-200 leading-relaxed whitespace-pre-wrap"
                  innerHTML={htmlContent()}
                />
              </div>
            </div>
          </div>
        </div>
      </Show>
    </div>
  );
};

export default ReasoningAccordion;
