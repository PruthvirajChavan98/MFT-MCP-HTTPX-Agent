import { For, Show, createSignal, onMount } from 'solid-js'
import { fetchModels, fetchSessionConfig, saveSessionConfig } from '../../features/admin/service'

export default function ModelConfigPage() {
  const [sessionId, setSessionId] = createSignal(localStorage.getItem('nbfc_chat_session_id') ?? 'session_demo')
  const [modelName, setModelName] = createSignal('')
  const [provider, setProvider] = createSignal('openrouter')
  const [reasoningEffort, setReasoningEffort] = createSignal('high')
  const [systemPrompt, setSystemPrompt] = createSignal('You are a compliant NBFC assistant.')

  const [models, setModels] = createSignal<Array<{ id: string; name: string; provider?: string }>>([])
  const [status, setStatus] = createSignal('')
  const [error, setError] = createSignal('')

  async function load(): Promise<void> {
    try {
      setError('')
      const [catalog, config] = await Promise.all([fetchModels(), fetchSessionConfig(sessionId())])
      const flat = catalog.flatMap((category) => category.models)
      setModels(flat)
      setModelName(config.model_name ?? flat[0]?.id ?? '')
      setProvider(config.provider ?? 'openrouter')
      setReasoningEffort(config.reasoning_effort ?? 'high')
      setSystemPrompt(config.system_prompt ?? 'You are a compliant NBFC assistant.')
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Failed to load config')
      setError(err.message)
    }
  }

  async function save(): Promise<void> {
    try {
      await saveSessionConfig({
        session_id: sessionId(),
        model_name: modelName(),
        provider: provider(),
        reasoning_effort: reasoningEffort(),
        system_prompt: systemPrompt(),
      })
      setStatus('Configuration saved')
    } catch (rawError) {
      const err = rawError instanceof Error ? rawError : new Error('Failed to save config')
      setError(err.message)
    }
  }

  onMount(() => {
    void load()
  })

  return (
    <section class="space-y-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Model Configuration</h1>
        <p class="text-sm text-slate-600">Session-bound provider/model controls via `/agent/config`.</p>
      </div>

      <div class="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 lg:grid-cols-2">
        <label class="text-xs text-slate-600">
          <span class="mb-1 block font-semibold">Session ID</span>
          <input value={sessionId()} onInput={(e) => setSessionId(e.currentTarget.value)} class="input-base w-full" />
        </label>

        <label class="text-xs text-slate-600">
          <span class="mb-1 block font-semibold">Model</span>
          <select value={modelName()} onChange={(e) => setModelName(e.currentTarget.value)} class="input-base w-full">
            <For each={models()}>{(model) => <option value={model.id}>{model.name} ({model.id})</option>}</For>
          </select>
        </label>

        <label class="text-xs text-slate-600">
          <span class="mb-1 block font-semibold">Provider</span>
          <select value={provider()} onChange={(e) => setProvider(e.currentTarget.value)} class="input-base w-full">
            <option value="openrouter">openrouter</option>
            <option value="groq">groq</option>
            <option value="nvidia">nvidia</option>
          </select>
        </label>

        <label class="text-xs text-slate-600">
          <span class="mb-1 block font-semibold">Reasoning Effort</span>
          <select value={reasoningEffort()} onChange={(e) => setReasoningEffort(e.currentTarget.value)} class="input-base w-full">
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        </label>

        <label class="text-xs text-slate-600 lg:col-span-2">
          <span class="mb-1 block font-semibold">System Prompt</span>
          <textarea value={systemPrompt()} onInput={(e) => setSystemPrompt(e.currentTarget.value)} class="input-base min-h-[140px] w-full" />
        </label>

        <div class="flex gap-2 lg:col-span-2">
          <button type="button" onClick={() => void save()} class="rounded-lg bg-cyan-600 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-700">Save Config</button>
          <button type="button" onClick={() => void load()} class="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:border-cyan-300">Reload</button>
        </div>
      </div>

      <Show when={status()}>
        <div class="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{status()}</div>
      </Show>
      <Show when={error()}>
        <div class="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error()}</div>
      </Show>
    </section>
  )
}
