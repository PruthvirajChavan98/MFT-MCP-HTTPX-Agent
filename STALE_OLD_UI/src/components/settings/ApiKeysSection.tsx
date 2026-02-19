import { Component, Show } from 'solid-js';
import { Cpu, Database, KeyRound, Zap } from 'lucide-solid';
import { Provider } from '../../types/domain';

interface ApiKeysSectionProps {
  provider: Provider;

  nvidiaKey: string;
  setNvidiaKey: (val: string) => void;
  hasNvidiaKey: boolean;

  openrouterKey: string;
  setOpenrouterKey: (val: string) => void;
  hasOpenRouterKey: boolean;

  groqKey: string;
  setGroqKey: (val: string) => void;
  hasGroqKey: boolean;
}

const ApiKeysSection: Component<ApiKeysSectionProps> = (props) => {
  return (
    <div class="space-y-4">

      {/* Groq Key Input */}
      <Show when={props.provider === 'groq'}>
        <div class="rounded-2xl border border-orange-200 bg-orange-50/50 p-4 text-sm text-slate-700 dark:border-orange-900/30 dark:bg-orange-900/10 dark:text-slate-200">
          <div class="flex items-center gap-2 font-semibold text-orange-700 dark:text-orange-400">
            <Zap size={16} />
            <span>Groq API Key</span>
            <Show when={props.hasGroqKey}>
              <span class="ml-auto rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">Saved</span>
            </Show>
          </div>
          <div class="mt-3">
            <input
              type="password"
              value={props.groqKey}
              onInput={(e) => props.setGroqKey(e.currentTarget.value)}
              placeholder={props.hasGroqKey ? 'Leave blank to keep existing' : 'gsk_...'}
              class="w-full rounded-xl border border-orange-300 bg-white px-4 py-2.5 text-sm font-mono focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500 dark:border-orange-800 dark:bg-slate-950 dark:text-white"
            />
          </div>
        </div>
      </Show>

      {/* NVIDIA Key Input */}
      <Show when={props.provider === 'nvidia'}>
        <div class="rounded-2xl border border-green-200 bg-green-50/50 p-4 text-sm text-slate-700 dark:border-green-900/30 dark:bg-green-900/10 dark:text-slate-200">
          <div class="flex items-center gap-2 font-semibold text-green-700 dark:text-green-400">
            <Cpu size={16} />
            <span>NVIDIA API Key</span>
            <Show when={props.hasNvidiaKey}>
              <span class="ml-auto rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">Saved</span>
            </Show>
          </div>
          <div class="mt-3">
            <input
              type="password"
              value={props.nvidiaKey}
              onInput={(e) => props.setNvidiaKey(e.currentTarget.value)}
              placeholder={props.hasNvidiaKey ? 'Leave blank to keep existing' : 'nvapi-...'}
              class="w-full rounded-xl border border-green-300 bg-white px-4 py-2.5 text-sm font-mono focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500 dark:border-green-800 dark:bg-slate-950 dark:text-white"
            />
          </div>
        </div>
      </Show>

      {/* OpenRouter Key Input */}
      <Show when={true}>
        <div class={props.provider === 'openrouter'
            ? 'rounded-2xl border border-indigo-200 bg-indigo-50/50 p-4 text-sm dark:border-indigo-900/30 dark:bg-indigo-900/10'
            : 'rounded-2xl border border-slate-200 bg-slate-50/50 p-4 text-sm dark:border-slate-800 dark:bg-slate-900/30'
        }>
          <div class="flex items-center gap-2 font-semibold text-slate-700 dark:text-slate-200">
            {props.provider === 'openrouter' ? <KeyRound size={16} class="text-indigo-600 dark:text-indigo-400" /> : <Database size={16} class="text-slate-400" />}
            <span>OpenRouter Key</span>
            <Show when={props.hasOpenRouterKey}>
              <span class="ml-auto rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">Saved</span>
            </Show>
          </div>
          <div class="mt-3">
            <input
              type="password"
              value={props.openrouterKey}
              onInput={(e) => props.setOpenrouterKey(e.currentTarget.value)}
              placeholder={props.hasOpenRouterKey ? 'Leave blank to keep existing' : 'sk-or-v1-...'}
              class="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-mono focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
            />
            <Show when={props.provider !== 'openrouter'}>
              <p class="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
                * Recommended for Embedding/Knowledge Base tools if using Groq/Nvidia.
              </p>
            </Show>
          </div>
        </div>
      </Show>

    </div>
  );
};

export default ApiKeysSection;
