import { Component, createMemo, createSignal, onCleanup, onMount, Show } from 'solid-js';
import { X, Save, Loader2, Settings2, AlertCircle } from 'lucide-solid';
import { agentService } from '../services/AgentService';
import { sessionState, sessionActions } from '../stores/sessionStore';
import type { Model, SessionConfig, Provider } from '../types/domain';
import { getParamOptions } from '../utils/modelCatalog';

import ModelConfigSection from './settings/ModelConfigSection';
import ApiKeysSection from './settings/ApiKeysSection';
import SystemPromptSection from './settings/SystemPromptSection';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

const DEFAULT_SYSTEM_PROMPT = 'You are a helpful assistant.';
export const CONFIG_UPDATED_EVENT = 'session-config-updated';
const PROVIDER_STORAGE_PREFIX = 'dual_stream_provider_';

const SettingsModal: Component<Props> = (props) => {
  const [allModels, setAllModels] = createSignal<Model[]>([]);
  const [systemPrompt, setSystemPrompt] = createSignal<string>(DEFAULT_SYSTEM_PROMPT);
  const [selectedModel, setSelectedModel] = createSignal<string>('');
  const [provider, setProvider] = createSignal<Provider>('groq');
  const [reasoningEffort, setReasoningEffort] = createSignal<string>('');

  const [loading, setLoading] = createSignal(true);
  const [saving, setSaving] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);

  // Local Key State
  const [keys, setKeys] = createSignal({
    openrouter: '',
    nvidia: '',
    groq: ''
  });

  const [hasKeys, setHasKeys] = createSignal({
    openrouter: false,
    nvidia: false,
    groq: false
  });

  let aborted = false;
  onCleanup(() => { aborted = true; });

  const providerModels = createMemo(() => allModels().filter(m => m.provider === provider()));
  const selectedModelObj = createMemo(() => providerModels().find(m => m.id === selectedModel()));
  const reasoningEffortOptions = createMemo(() => getParamOptions(selectedModelObj(), 'reasoning_effort'));
  const selectedSupportsReasoningEffort = createMemo(() => Array.isArray(reasoningEffortOptions()) && reasoningEffortOptions()!.length > 0);

  onMount(async () => {
    try {
      if (!sessionState.sessionId) throw new Error('No session ID');

      const [models, cfg] = await Promise.all([
        agentService.getModels(),
        agentService.getSessionConfig(sessionState.sessionId)
      ]);

      if (aborted) return;
      setAllModels(models);

      setSystemPrompt(cfg.system_prompt || DEFAULT_SYSTEM_PROMPT);
      setSelectedModel(cfg.model_name || '');
      setProvider(cfg.provider || 'groq');
      setReasoningEffort(cfg.reasoning_effort || '');

      setHasKeys({
        openrouter: !!cfg.has_openrouter_key,
        nvidia: !!cfg.has_nvidia_key,
        groq: !!cfg.has_groq_key
      });

      // Load local keys from store
      const storedKeys = sessionActions.getKeys();
      setKeys({
        openrouter: storedKeys.openrouter || '',
        nvidia: storedKeys.nvidia || '',
        groq: storedKeys.groq || ''
      });

    } catch (e: any) {
      if (!aborted) setError(e.message);
    } finally {
      if (!aborted) setLoading(false);
    }
  });

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      if (!selectedModel()) throw new Error("Please select a model.");

      const payload: SessionConfig = {
        session_id: sessionState.sessionId,
        model_name: selectedModel(),
        provider: provider(),
        system_prompt: systemPrompt(),
        reasoning_effort: reasoningEffort() || null,
        openrouter_api_key: keys().openrouter || undefined,
        nvidia_api_key: keys().nvidia || undefined,
        groq_api_key: keys().groq || undefined,
      };

      await agentService.updateSessionConfig(payload);

      sessionActions.setConfig(payload);
      sessionActions.saveKeys({
        openrouter: keys().openrouter,
        nvidia: keys().nvidia,
        groq: keys().groq
      });

      window.dispatchEvent(new CustomEvent(CONFIG_UPDATED_EVENT, { detail: payload }));
      props.onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div class="w-full max-w-4xl rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-800 flex flex-col max-h-[90vh]">

        <div class="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-6 py-4">
          <div class="flex items-center gap-2 text-slate-900 dark:text-white font-semibold">
            <Settings2 size={20} /><span>Session Configuration</span>
          </div>
          <button onClick={props.onClose} class="text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"><X size={20} /></button>
        </div>

        <div class="flex-1 overflow-y-auto p-6 space-y-6">
          <Show when={loading()}><div class="flex justify-center p-8"><Loader2 class="animate-spin text-indigo-500" /></div></Show>
          <Show when={!loading()}>
            {error() && <div class="bg-red-50 text-red-600 p-3 rounded-lg text-sm border border-red-100 flex items-center gap-2"><AlertCircle size={16} /> {error()}</div>}

            <ModelConfigSection
              allModels={allModels()}
              provider={provider()}
              setProvider={setProvider}
              selectedModel={selectedModel()}
              setSelectedModel={setSelectedModel}
              providerModels={providerModels()}
              selectedModelObj={selectedModelObj()}
              reasoningEffort={reasoningEffort()}
              setReasoningEffort={setReasoningEffort}
              reasoningEffortOptions={reasoningEffortOptions()}
              supportsReasoningEffort={selectedSupportsReasoningEffort()}
            />

            <ApiKeysSection
              provider={provider()}
              nvidiaKey={keys().nvidia}
              setNvidiaKey={(k) => setKeys(p => ({...p, nvidia: k}))}
              hasNvidiaKey={hasKeys().nvidia}
              openrouterKey={keys().openrouter}
              setOpenrouterKey={(k) => setKeys(p => ({...p, openrouter: k}))}
              hasOpenRouterKey={hasKeys().openrouter}
              groqKey={keys().groq}
              setGroqKey={(k) => setKeys(p => ({...p, groq: k}))}
              hasGroqKey={hasKeys().groq}
            />

            <SystemPromptSection
              systemPrompt={systemPrompt()}
              setSystemPrompt={setSystemPrompt}
              defaultPrompt={DEFAULT_SYSTEM_PROMPT}
            />
          </Show>
        </div>

        <div class="border-t border-slate-200 dark:border-slate-800 px-6 py-4 flex justify-end gap-3">
          <button onClick={props.onClose} class="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg">Cancel</button>
          <button onClick={handleSave} disabled={saving() || !selectedModel()} class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50">
            {saving() ? <Loader2 size={16} class="animate-spin" /> : <Save size={16} />} Save Changes
          </button>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;
