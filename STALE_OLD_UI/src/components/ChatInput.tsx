// src/components/ChatInput.tsx
import { Component, createSignal, Show, onMount, onCleanup } from 'solid-js'; // ✅ Import onMount/onCleanup
import { Send, StopCircle, AlertTriangle, Sparkles } from 'lucide-solid';
import { chatState, chatActions } from '../stores/chat';

interface ChatInputProps {
  onSend: (text: string) => void;
  error: string | null;
}

const ChatInput: Component<ChatInputProps> = (props) => {
  let inputRef: HTMLTextAreaElement | undefined;

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (!chatState.input.trim() || chatState.isGenerating) return;
    props.onSend(chatState.input);

    // Reset height
    if (inputRef) {
        inputRef.style.height = 'auto';
        inputRef.focus();
    }
  };

  // ✅ NEW: Listen for auto-send events from Markdown links
  onMount(() => {
    const handleAutoSubmit = () => handleSubmit();
    window.addEventListener('chat:submit', handleAutoSubmit);
    onCleanup(() => window.removeEventListener('chat:submit', handleAutoSubmit));
  });

  return (
    <footer class="relative z-20 border-t border-slate-200 bg-white/90 p-4 backdrop-blur dark:border-slate-800 dark:bg-slate-900/90">
      <div class="mx-auto flex max-w-6xl flex-col gap-2">
        <Show when={props.error}>
          <div class="flex items-center gap-2 rounded-md bg-red-50 p-2 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400 animate-slide-up">
            <AlertTriangle size={14} />
            <span>{props.error}</span>
          </div>
        </Show>

        <div class="relative flex items-end gap-2 rounded-2xl border border-slate-300 bg-white p-2 shadow-sm focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 transition-all dark:border-slate-700 dark:bg-slate-950">
          <textarea
            id="chat-input-textarea"
            ref={(el) => (inputRef = el)}
            rows={1}
            value={chatState.input}
            onInput={(e) => {
              chatActions.setInput(e.currentTarget.value);
              e.currentTarget.style.height = 'auto';
              e.currentTarget.style.height = `${Math.min(e.currentTarget.scrollHeight, 200)}px`;
            }}
            onKeyDown={handleKeyDown}
            placeholder="Message Dual-Stream AI..."
            class="max-h-50 w-full resize-none bg-transparent px-3 py-3 text-sm focus:outline-none dark:text-white dark:placeholder-slate-500"
            disabled={chatState.isGenerating}
            autofocus
          />
          <button
            onClick={handleSubmit}
            disabled={!chatState.input.trim() || chatState.isGenerating}
            class="mb-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white transition-all hover:bg-indigo-700 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed dark:disabled:bg-slate-800 dark:disabled:text-slate-600"
          >
            <Show
              when={!chatState.isGenerating}
              fallback={<StopCircle size={20} class="animate-pulse" />}
            >
              <Send size={20} />
            </Show>
          </button>
        </div>

        <div class="text-center text-[10px] text-slate-400 flex items-center justify-center gap-2">
          <Sparkles size={10} />
          <span>Dual-Stream Architecture (Reasoning + Response)</span>
        </div>
      </div>
    </footer>
  );
};

export default ChatInput;
