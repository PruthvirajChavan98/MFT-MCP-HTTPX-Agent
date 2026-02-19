import { Component, For, Show } from 'solid-js';
import { Model, Provider } from '../../types/chat';
import { isReasoningCapable, isToolCallingCapable } from '../../utils/modelCatalog';

interface ModelConfigSectionProps {
  allModels: Model[];
  provider: Provider;
  setProvider: (p: Provider) => void;
  selectedModel: string;
  setSelectedModel: (id: string) => void;
  providerModels: Model[];
  selectedModelObj?: Model;
  reasoningEffort: string;
  setReasoningEffort: (val: string) => void;
  reasoningEffortOptions: string[] | null;
  supportsReasoningEffort: boolean;
}

const fmtUSD = (n: number) =>
  '$' + (n < 1 ? n.toFixed(3) : n.toFixed(2)).replace(/\.?0+$/, '');

const fmtPricing = (m: Model) => {
  if (!m.pricing) return '';
  return `P ${fmtUSD(m.pricing.prompt)} · C ${fmtUSD(m.pricing.completion)} / 1M`;
};

const ModelConfigSection: Component<ModelConfigSectionProps> = (props) => {
  return (
    <>
      {/* Provider */}
      <div class="space-y-2">
        <label class="block text-sm font-medium text-slate-700 dark:text-slate-300">
          Provider
        </label>
        <select
          value={props.provider}
          onChange={(e) => props.setProvider(e.currentTarget.value as Provider)}
          class="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
        >
          {/* ✅ FIX: Consistent BYOK naming */}
          <option value="groq">Groq (BYOK)</option>
          <option value="nvidia">NVIDIA NIM (BYOK)</option>
          <option value="openrouter">OpenRouter (BYOK)</option>
        </select>
      </div>

      {/* Model selector */}
      <div class="space-y-2">
        <label class="block text-sm font-medium text-slate-700 dark:text-slate-300">
          Models
        </label>

        <select
          value={props.selectedModel}
          onChange={(e) => props.setSelectedModel(e.currentTarget.value)}
          class="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
        >
          <option value="" disabled>
            Select a model…
          </option>

          <For each={props.providerModels}>
            {(m) => (
              <option value={m.id}>
                {isReasoningCapable(m) ? '🧠 ' : ''}
                {isToolCallingCapable(m) ? '🛠️ ' : ''}
                {m.name ?? m.id}
                {m.pricing ? ` · ${fmtPricing(m)}` : ''}
              </option>
            )}
          </For>
        </select>

        <p class="text-xs text-slate-500">
          Pricing shown as USD per 1M tokens (prompt vs completion).{' '}
          <span class="ml-2">🧠 = reasoning-capable.</span>
        </p>
      </div>

      {/* Selected model details */}
      <Show when={props.selectedModelObj}>
        <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200">
          <div class="flex items-center justify-between gap-3">
            <div class="font-semibold">Selected Model</div>
            <Show when={props.selectedModelObj && isReasoningCapable(props.selectedModelObj!)}>
              <span class="rounded-full bg-indigo-100 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
                🧠 Reasoning
              </span>
            </Show>
          </div>

          <div class="mt-3 space-y-1 text-xs">
            <div class="flex items-center justify-between gap-3">
              <span class="text-slate-500 dark:text-slate-400">Provider</span>
              <span class="font-mono text-[11px]">{props.selectedModelObj?.provider}</span>
            </div>
            <div class="flex items-center justify-between gap-3">
              <span class="text-slate-500 dark:text-slate-400">Model</span>
              <span class="font-mono text-[11px]">{props.selectedModelObj?.id}</span>
            </div>
            <Show when={props.selectedModelObj?.contextLength}>
              <div class="flex items-center justify-between gap-3">
                <span class="text-slate-500 dark:text-slate-400">Context Window</span>
                <span class="font-mono text-[11px]">
                  {Math.round(props.selectedModelObj!.contextLength! / 1000)}k tokens
                </span>
              </div>
            </Show>
          </div>
        </div>
      </Show>

      {/* Reasoning Effort (Conditional) */}
      <Show when={props.selectedModelObj && props.supportsReasoningEffort}>
        <div class="space-y-2">
          <label class="block text-sm font-medium text-slate-700 dark:text-slate-300">
            reasoning_effort
          </label>
          <select
            value={props.reasoningEffort}
            onChange={(e) => props.setReasoningEffort(e.currentTarget.value)}
            class="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
          >
            <For each={props.reasoningEffortOptions ?? []}>
              {(opt) => <option value={opt}>{opt}</option>}
            </For>
          </select>
        </div>
      </Show>
    </>
  );
};

export default ModelConfigSection;
