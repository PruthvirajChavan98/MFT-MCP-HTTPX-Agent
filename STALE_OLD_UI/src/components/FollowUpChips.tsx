// src/components/FollowUpChips.tsx
import { Component, For, Show } from 'solid-js';
import { MessageSquarePlus, Loader2, Info } from 'lucide-solid';
import type { FollowUpCandidate } from '../types/chat';

interface FollowUpChipsProps {
  candidates: FollowUpCandidate[];
  isGenerating: boolean;
  status?: string | null;
  onSelect: (question: string) => void;
}

const FollowUpChips: Component<FollowUpChipsProps> = (props) => {
  const list = () => props.candidates ?? [];
  const isVisible = () => list().length > 0 || !!props.status;

  return (
    <Show when={isVisible()}>
      <div class="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/50 animate-fade-in">

        {/* Header */}
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            <MessageSquarePlus size={12} />
            <span>Suggested Questions</span>
          </div>

          <Show when={props.status}>
            <div class="flex items-center gap-1.5 text-[10px] text-indigo-500/80 dark:text-indigo-400/80 animate-pulse font-medium">
              <Loader2 size={10} class="animate-spin" />
              <span>{props.status}</span>
            </div>
          </Show>
        </div>

        {/* Links Grid */}
        <Show when={list().length > 0}>
          <div class="flex flex-wrap gap-x-6 gap-y-3 justify-center">
            <For each={list()}>
              {(c) => {
                const hasReasoning = () => (c.why ?? '').trim().length > 0;

                return (
                  <div class="flex items-center gap-1.5 group relative">
                    {/* 1. Question as a Link */}
                    <button
                      onClick={() => props.onSelect(c.question)}
                      disabled={props.isGenerating}
                      class="text-xs sm:text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 hover:underline underline-offset-4 decoration-indigo-300/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-left"
                    >
                      {c.question}
                    </button>

                    {/* 2. Info Icon with Tooltip */}
                    <Show when={hasReasoning()}>
                      <div class="relative group/tooltip flex items-center cursor-help">
                        <Info
                          size={14}
                          class="text-slate-300 hover:text-indigo-500 transition-colors"
                        />

                        {/* Tooltip Popup */}
                        <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2.5 bg-slate-900/95 text-slate-100 text-[10px] leading-relaxed rounded-lg shadow-xl backdrop-blur-sm opacity-0 group-hover/tooltip:opacity-100 transition-opacity duration-200 pointer-events-none z-50 border border-slate-700/50 whitespace-normal">
                          {c.why}

                          <Show when={c.whyDone === false}>
                             <span class="inline-block w-1.5 h-3 ml-1 align-middle bg-indigo-400 animate-pulse rounded-sm"></span>
                          </Show>

                          {/* Arrow */}
                          <div class="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-slate-900/95"></div>
                        </div>
                      </div>
                    </Show>
                  </div>
                );
              }}
            </For>
          </div>
        </Show>
      </div>
    </Show>
  );
};

export default FollowUpChips;
