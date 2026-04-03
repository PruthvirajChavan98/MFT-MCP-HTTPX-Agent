import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Bot,
  MessageCircle,
  X,
  Trash2,
  Settings,
  ArrowLeft,
  Save,
  Loader2,
  KeyRound,
  Maximize2,
  Minimize2,
  AlertTriangle,
  Sparkles,
  Plus,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { useChatStream } from '@features/chat/hooks/useChatStream'
import {
  fetchSessionConfig,
  saveSessionConfig,
  type AgentModel,
  type SessionConfig,
} from '@features/admin/api/admin'
import { useAvailableModels } from '@shared/hooks/useModels'
import { cn } from '@components/ui/utils'

const STARTER_PROMPTS = [
  {
    label: 'Home loan rates',
    text: 'What are your current home loan interest rates and processing fees?',
  },
  {
    label: 'EMI planning',
    text: 'Help me estimate EMI options for a 40 lakh loan over 15, 20, and 25 years.',
  },
  {
    label: 'Business loan docs',
    text: 'Which documents do you need for a secured business loan application?',
  },
  {
    label: 'Application tracking',
    text: 'How do I check the status of my current loan application?',
  },
] as const

function providerRequiresSessionKey(provider: string) {
  return provider === 'openrouter' || provider === 'nvidia'
}

function hasSavedProviderKey(provider: string, sessionCfg?: SessionConfig) {
  if (provider === 'openrouter') return !!sessionCfg?.has_openrouter_key
  if (provider === 'nvidia') return !!sessionCfg?.has_nvidia_key
  if (provider === 'groq') return !!sessionCfg?.has_groq_key
  return false
}

function providerKeyHeading(provider: string) {
  if (provider === 'openrouter') return 'OpenRouter Key (Required)'
  if (provider === 'nvidia') return 'NVIDIA Key (Required)'
  return 'Groq Key (Optional)'
}

function providerKeyHelp(provider: string, hasSavedKey: boolean) {
  if (provider === 'openrouter') {
    return hasSavedKey
      ? 'A saved OpenRouter key already exists for this session. Leave blank to keep it, or enter a new one to replace it.'
      : 'OpenRouter sessions require a key. Enter one now to save and apply this model.'
  }
  if (provider === 'nvidia') {
    return hasSavedKey
      ? 'A saved NVIDIA key already exists for this session. Leave blank to keep it, or enter a new one to replace it.'
      : 'NVIDIA sessions require a key. Enter one now to save and apply this model.'
  }
  return hasSavedKey
    ? 'A saved Groq key already exists for this session. Leave blank to keep it, or enter a new one to replace it.'
    : 'Groq BYOK is optional. Leave blank to use the server-managed Groq key.'
}

// --- Settings View Component ---
function ChatSettingsView({ sessionId, onBack }: { sessionId: string; onBack: () => void }) {
  const qc = useQueryClient()

  const [formData, setFormData] = useState({
    provider: 'groq',
    model_name: '',
    reasoning_effort: 'medium',
    system_prompt: '',
    apiKey: '',
  })

  const handleModelChange = useCallback((newModelId: string) => {
    setFormData((prev) => ({ ...prev, model_name: newModelId }))
  }, [])

  const { availableModels, isLoading: mLoading } = useAvailableModels(
    formData.provider,
    formData.model_name,
    handleModelChange,
  )
  const selectedModel = availableModels.find((model) => model.id === formData.model_name) as
    | AgentModel
    | undefined

  const { data: sessionCfg, isLoading: cfgLoading } = useQuery({
    queryKey: ['session-config', sessionId],
    queryFn: () => fetchSessionConfig(sessionId),
    enabled: !!sessionId,
  })

  useEffect(() => {
    setFormData({
      provider: sessionCfg?.provider || 'groq',
      model_name: sessionCfg?.model_name || '',
      reasoning_effort: sessionCfg?.reasoning_effort || 'medium',
      system_prompt: sessionCfg?.system_prompt || '',
      apiKey: '',
    })
  }, [sessionCfg])

  const requiresProviderKey = providerRequiresSessionKey(formData.provider)
  const savedProviderKey = hasSavedProviderKey(formData.provider, sessionCfg)
  const hasNewProviderKey = formData.apiKey.trim().length > 0
  const canSave = !!formData.model_name && (!requiresProviderKey || savedProviderKey || hasNewProviderKey)

  const saveMut = useMutation({
    mutationFn: async () => {
      const payload: any = {
        session_id: sessionId,
        provider: formData.provider,
        model_name: formData.model_name,
        reasoning_effort: formData.reasoning_effort,
        system_prompt: formData.system_prompt,
      }

      if (formData.apiKey) {
        if (formData.provider === 'openrouter') payload.openrouter_api_key = formData.apiKey
        else if (formData.provider === 'nvidia') payload.nvidia_api_key = formData.apiKey
        else if (formData.provider === 'groq') payload.groq_api_key = formData.apiKey
      }

      return saveSessionConfig(payload)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['session-config', sessionId] })
      toast.success('Session settings updated')
      onBack()
    },
    onError: (error) => toast.error((error as Error).message),
  })

  if (mLoading || cfgLoading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center bg-slate-50 text-slate-500">
        <Loader2 className="mb-2 h-6 w-6 animate-spin text-cyan-600" />
        <p className="text-sm font-medium">Loading session config...</p>
      </div>
    )
  }

  return (
    <div className="flex-1 space-y-5 overflow-y-auto bg-slate-50 p-5">
      <div className="space-y-1.5">
        <label className="text-xs font-bold uppercase tracking-wider text-slate-700">Provider</label>
        <select
          value={formData.provider}
          onChange={(e) => setFormData({ ...formData, provider: e.target.value, model_name: '' })}
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition-shadow focus:ring-2 focus:ring-cyan-500"
        >
          <option value="groq">Groq (Fastest)</option>
          <option value="openrouter">OpenRouter (Most Models)</option>
          <option value="nvidia">NVIDIA NIM</option>
        </select>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-bold uppercase tracking-wider text-slate-700">Model</label>
        <select
          value={formData.model_name}
          onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition-shadow focus:ring-2 focus:ring-cyan-500"
        >
          <option value="" disabled>
            Select a model...
          </option>
          {availableModels.map((model: any) => (
            <option key={model.id} value={model.id}>
              {model.display_name || model.name || model.id}
            </option>
          ))}
        </select>
        <p className="text-[10px] leading-tight text-slate-500">
          {selectedModel?.supports_tools
            ? 'This model supports tool calling.'
            : 'This model is chat-only.'}
        </p>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-bold uppercase tracking-wider text-slate-700">
          Reasoning Effort
        </label>
        <select
          value={formData.reasoning_effort}
          onChange={(e) => setFormData({ ...formData, reasoning_effort: e.target.value })}
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition-shadow focus:ring-2 focus:ring-cyan-500"
        >
          <option value="low">Low (Fastest)</option>
          <option value="medium">Medium (Balanced)</option>
          <option value="high">High (Deep Thinking)</option>
        </select>
        <p className="text-[10px] leading-tight text-slate-500">
          {selectedModel?.supports_reasoning_effort
            ? 'Applied when the selected model supports reasoning effort.'
            : 'Visible for all models; unsupported models ignore the saved setting.'}
        </p>
      </div>

      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-700">
          <KeyRound size={12} /> {providerKeyHeading(formData.provider)}
        </label>
        <input
          type="password"
          value={formData.apiKey}
          onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
          placeholder={`Enter ${formData.provider} API Key`}
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 font-mono text-sm text-slate-900 shadow-sm outline-none transition-shadow placeholder:font-sans focus:ring-2 focus:ring-cyan-500"
        />
        <p className="text-[10px] leading-tight text-slate-500">
          {providerKeyHelp(formData.provider, savedProviderKey)}
        </p>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-bold uppercase tracking-wider text-slate-700">System Prompt</label>
        <textarea
          value={formData.system_prompt}
          onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
          placeholder="You are a helpful assistant..."
          rows={5}
          className="w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2.5 font-mono text-sm text-slate-900 shadow-sm outline-none transition-shadow focus:ring-2 focus:ring-cyan-500"
        />
      </div>

      <button
        onClick={() => saveMut.mutate()}
        disabled={saveMut.isPending || !canSave}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-teal-500 py-3 font-semibold text-white shadow-lg transition-opacity disabled:opacity-50"
        type="button"
      >
        {saveMut.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
        Save & Apply
      </button>
    </div>
  )
}

// --- Main Chat Widget ---
export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [isMaximized, setIsMaximized] = useState(false)
  const [view, setView] = useState<'chat' | 'settings'>('chat')
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { messages, isStreaming, error, sendMessage, stopGeneration, clearConversation, sessionId } =
    useChatStream()

  useEffect(() => {
    if (!isOpen || view !== 'chat') return
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming, error, isOpen, view, isMaximized])

  const handleSend = () => {
    if (!input.trim() || isStreaming) return
    sendMessage(input)
    setInput('')
  }

  const handleFollowUp = (text: string) => {
    if (isStreaming) return
    sendMessage(text)
  }

  const handleNewConversation = () => {
    clearConversation()
    setInput('')
  }

  const closeWidget = () => {
    setIsOpen(false)
    setIsMaximized(false)
    setView('chat')
  }

  return (
    <>
      <AnimatePresence>
        {isOpen && (
          <>
            {isMaximized && (
              <motion.div
                animate={{ opacity: 1 }}
                className="fixed inset-0 z-40 bg-slate-900/45 backdrop-blur-sm"
                exit={{ opacity: 0 }}
                initial={{ opacity: 0 }}
                onClick={() => setIsMaximized(false)}
              />
            )}

            <motion.div
              layout
              animate={{ opacity: 1, scale: 1, y: 0 }}
              className={cn(
                'tf-chat-widget z-50 flex origin-bottom-right flex-col overflow-hidden border border-slate-200 bg-white shadow-2xl transition-all',
                isMaximized
                  ? 'fixed inset-4 rounded-2xl sm:inset-10'
                  : 'fixed bottom-6 right-6 h-[590px] max-h-[calc(100vh-8rem)] w-[390px] max-w-[calc(100vw-1.5rem)] rounded-3xl',
              )}
              exit={{ opacity: 0, scale: 0.9, y: 18 }}
              initial={{ opacity: 0, scale: 0.9, y: 18 }}
              transition={{ type: 'spring', stiffness: 320, damping: 32 }}
            >
              <header className="relative z-10 flex shrink-0 items-center justify-between border-b border-cyan-400/20 bg-gradient-to-r from-cyan-500 to-teal-500 p-4 text-white">
                <div className="flex min-w-0 items-center gap-3">
                  {view === 'settings' ? (
                    <button
                      className="-ml-1 inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-white/20"
                      onClick={() => setView('chat')}
                      title="Back to chat"
                      type="button"
                    >
                      <ArrowLeft size={18} />
                    </button>
                  ) : (
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/25 bg-white/20 shadow-inner backdrop-blur-sm">
                      <Sparkles size={18} />
                    </div>
                  )}

                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-sm font-bold tracking-tight">
                      {view === 'settings' ? 'Session Configuration' : 'Mock FinTech Assistant'}
                    </h3>
                    {view === 'chat' && (
                      <p className="mt-0.5 flex items-center gap-1.5 text-xs font-medium text-white/85">
                        <span
                          className={cn(
                            'h-1.5 w-1.5 rounded-full',
                            isStreaming ? 'animate-pulse bg-yellow-300' : 'bg-emerald-300',
                          )}
                        />
                        {isStreaming ? 'Generating...' : 'Online'}
                      </p>
                    )}
                  </div>
                </div>

                <div className="ml-2 flex items-center gap-1">
                  {view === 'chat' && (
                    <>
                      <button
                        className="inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-white/20"
                        onClick={handleNewConversation}
                        title="New chat"
                        type="button"
                      >
                        <Plus size={15} />
                      </button>
                      {messages.length > 0 && (
                        <button
                          className="inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-white/20"
                          onClick={clearConversation}
                          title="Clear chat"
                          type="button"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                      <button
                        className="inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-white/20"
                        onClick={() => setView('settings')}
                        title="Configure session"
                        type="button"
                      >
                        <Settings size={15} />
                      </button>
                    </>
                  )}

                  <button
                    className="hidden h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-white/20 sm:inline-flex"
                    onClick={() => setIsMaximized((prev) => !prev)}
                    title={isMaximized ? 'Minimize' : 'Maximize'}
                    type="button"
                  >
                    {isMaximized ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                  </button>

                  <button
                    className="ml-1 inline-flex h-8 w-8 items-center justify-center rounded-full bg-black/10 transition-colors hover:bg-black/20"
                    onClick={closeWidget}
                    title="Close chat"
                    type="button"
                  >
                    <X size={16} />
                  </button>
                </div>
              </header>

              {view === 'settings' ? (
                <ChatSettingsView onBack={() => setView('chat')} sessionId={sessionId} />
              ) : (
                <>
                  <div className="flex-1 overflow-y-auto bg-slate-50/80">
                    <div className="mx-auto flex h-full max-w-3xl flex-col gap-5 px-4 py-5 sm:px-5">
                      {messages.length === 0 && !isStreaming ? (
                        <div className="flex h-full flex-col items-center justify-center px-2 py-8 text-center">
                          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-cyan-200 bg-gradient-to-br from-cyan-100 to-teal-100 text-cyan-700 shadow-sm">
                            <Bot size={24} />
                          </div>
                          <h4 className="text-lg font-semibold text-slate-900">What can I help you with?</h4>
                          <p className="mt-2 max-w-[270px] text-sm leading-6 text-slate-500">
                            Ask about rates, loan eligibility, repayment plans, and your current application status.
                          </p>

                          <div className="mt-5 grid w-full max-w-[560px] grid-cols-1 gap-2.5 sm:grid-cols-2">
                            {STARTER_PROMPTS.map((prompt) => (
                              <button
                                className="inline-flex items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-left text-[13px] font-medium text-slate-600 shadow-sm transition hover:border-cyan-300 hover:bg-cyan-50/60 hover:text-slate-900"
                                key={prompt.label}
                                onClick={() => handleFollowUp(prompt.text)}
                                type="button"
                              >
                                <span>{prompt.label}</span>
                                <span aria-hidden className="text-slate-400">
                                  →
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <>
                          {messages.map((message) => (
                            <ChatMessage key={message.id} message={message} sessionId={sessionId} onFollowUpClick={handleFollowUp} />
                          ))}
                        </>
                      )}

                      {error && (
                        <div className="flex items-center gap-2 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-xs text-red-600 shadow-sm">
                          <AlertTriangle size={14} className="shrink-0" />
                          <p>{error}</p>
                        </div>
                      )}

                      <div ref={messagesEndRef} className="h-px w-full" />
                    </div>
                  </div>

                  <ChatInput
                    isStreaming={isStreaming}
                    onChange={setInput}
                    onSend={handleSend}
                    onStop={stopGeneration}
                    value={input}
                  />
                </>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {!isOpen && (
        <motion.button
          whileHover={{ scale: 1.05, y: -2 }}
          whileTap={{ scale: 0.95 }}
          aria-label="Open chat"
          className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full border border-white/20 bg-gradient-to-br from-cyan-500 to-teal-600 text-white shadow-2xl transition-all"
          data-highlight-id="landing-chat-launcher"
          onClick={() => setIsOpen(true)}
        >
          <motion.span
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.5, opacity: 0 }}
            initial={{ scale: 0.5, opacity: 0 }}
            transition={{ duration: 0.15 }}
          >
            <MessageCircle size={24} />
          </motion.span>

          {messages.length > 0 && (
            <span className="absolute right-0 top-0 h-3.5 w-3.5 animate-pulse rounded-full border-2 border-white bg-red-500" />
          )}
        </motion.button>
      )}
    </>
  )
}
