import { useState, useRef, useEffect, useCallback } from 'react'
import { Bot, MessageCircle, X, Trash2, Settings, ArrowLeft, Save, Loader2, KeyRound, Maximize2, Minimize2, AlertTriangle } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { useChatStream } from '../../shared/hooks/useChatStream'
import { fetchSessionConfig, saveSessionConfig } from '../../shared/api/admin'
import { useAvailableModels } from '../../shared/hooks/useModels'
import { cn } from './ui/utils'

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
    setFormData((prev) => ({ ...prev, model_name: newModelId }));
  }, []);

  const { availableModels, isLoading: mLoading } = useAvailableModels(
    formData.provider,
    formData.model_name,
    handleModelChange
  );

  const { isLoading: cfgLoading } = useQuery({
    queryKey: ['session-config', sessionId],
    queryFn: () => fetchSessionConfig(sessionId),
    enabled: !!sessionId,
  })

  useEffect(() => {
    const cachedCfg = qc.getQueryData<any>(['session-config', sessionId])
    if (cachedCfg) {
      setFormData({
        provider: cachedCfg.provider || 'groq',
        model_name: cachedCfg.model_name || '',
        reasoning_effort: cachedCfg.reasoning_effort || 'medium',
        system_prompt: cachedCfg.system_prompt || '',
        apiKey: '',
      })
    }
  }, [sessionId, qc])

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
    onError: (e) => toast.error((e as Error).message),
  })

  if (mLoading || cfgLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-gray-50/40 text-gray-500">
        <Loader2 className="w-6 h-6 animate-spin mb-2 text-cyan-600" />
        <p className="text-sm font-medium">Loading config...</p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50/40 p-5 space-y-5">
      <div className="space-y-1.5">
        <label className="text-xs font-bold text-gray-700 uppercase tracking-wider">Provider</label>
        <select
          value={formData.provider}
          onChange={(e) => setFormData({ ...formData, provider: e.target.value, model_name: '' })}
          className="w-full bg-white border border-gray-200 rounded-xl px-3 py-2.5 text-sm text-gray-900 focus:ring-2 focus:ring-cyan-500 outline-none transition-shadow shadow-sm"
        >
          <option value="groq">Groq (Fastest)</option>
          <option value="openrouter">OpenRouter (Most Models)</option>
          <option value="nvidia">NVIDIA NIM</option>
        </select>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-bold text-gray-700 uppercase tracking-wider">Model</label>
        <select
          value={formData.model_name}
          onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
          className="w-full bg-white border border-gray-200 rounded-xl px-3 py-2.5 text-sm text-gray-900 focus:ring-2 focus:ring-cyan-500 outline-none transition-shadow shadow-sm"
        >
          <option value="" disabled>Select a model...</option>
          {availableModels.map((m: any) => (
            <option key={m.id} value={m.id}>{m.name}</option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
          <KeyRound size={12} /> Bring Your Own Key (Optional)
        </label>
        <input
          type="password"
          value={formData.apiKey}
          onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
          placeholder={`Enter ${formData.provider} API Key`}
          className="w-full bg-white border border-gray-200 rounded-xl px-3 py-2.5 text-sm text-gray-900 font-mono focus:ring-2 focus:ring-cyan-500 outline-none transition-shadow shadow-sm placeholder:font-sans"
        />
        <p className="text-[10px] text-gray-500 leading-tight">
          Leave blank to use server defaults. Keys are securely bound to this session.
        </p>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-bold text-gray-700 uppercase tracking-wider">System Prompt</label>
        <textarea
          value={formData.system_prompt}
          onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
          placeholder="You are a helpful assistant..."
          rows={4}
          className="w-full bg-white border border-gray-200 rounded-xl px-3 py-2.5 text-sm text-gray-900 focus:ring-2 focus:ring-cyan-500 outline-none transition-shadow shadow-sm resize-none font-mono"
        />
      </div>

      <button
        onClick={() => saveMut.mutate()}
        disabled={saveMut.isPending || !formData.model_name}
        className="w-full py-3 rounded-xl text-white font-semibold flex items-center justify-center gap-2 shadow-lg disabled:opacity-50 transition-opacity bg-gradient-to-r from-cyan-500 to-teal-500"
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

  const { messages, followUps, isStreaming, error, sendMessage, stopGeneration, clearConversation, sessionId } =
    useChatStream()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    if (isOpen && view === 'chat') scrollToBottom()
  }, [messages, isStreaming, isOpen, view, isMaximized])

  const handleSend = () => {
    if (!input.trim() || isStreaming) return
    sendMessage(input)
    setInput('')
  }

  const handleFollowUp = (text: string) => {
    sendMessage(text)
  }

  return (
    <>
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop for maximized mode */}
            {isMaximized && (
              <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40"
                onClick={() => setIsMaximized(false)}
              />
            )}

            <motion.div
              layout
              initial={{ opacity: 0, scale: 0.85, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.85, y: 20 }}
              transition={{ type: 'spring', stiffness: 350, damping: 30 }}
              className={cn(
                "bg-white shadow-2xl flex flex-col overflow-hidden border border-gray-200/60 z-50 transition-all origin-bottom-right",
                isMaximized
                  ? "fixed inset-4 sm:inset-10 rounded-2xl"
                  : "fixed bottom-6 right-6 w-[380px] max-w-[calc(100vw-2rem)] h-[560px] max-h-[calc(100vh-8rem)] rounded-3xl"
              )}
            >
              {/* Header */}
              <div className="bg-gradient-to-r from-cyan-500 to-teal-500 text-white p-4 flex items-center justify-between flex-shrink-0 shadow-sm relative z-10">
                <div className="flex items-center gap-3 min-w-0">
                  {view === 'settings' ? (
                    <button onClick={() => setView('chat')} className="w-8 h-8 -ml-1 rounded-full hover:bg-white/20 flex items-center justify-center transition-colors">
                      <ArrowLeft size={18} className="text-white" />
                    </button>
                  ) : (
                    <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm border border-white/20 shadow-inner">
                      <Bot size={20} className="text-white drop-shadow-sm" />
                    </div>
                  )}

                  <div className="flex-1 min-w-0">
                    <h3 className="font-bold text-sm tracking-tight truncate">
                      {view === 'settings' ? 'Session Configuration' : 'TrustFin Assistant'}
                    </h3>
                    {view === 'chat' && (
                      <p className="text-white/80 text-xs font-medium flex items-center gap-1.5 mt-0.5">
                        <span className={cn('w-1.5 h-1.5 rounded-full shadow-sm', isStreaming ? 'bg-yellow-300 animate-pulse' : 'bg-green-400')} />
                        {isStreaming ? 'Generating…' : 'Online'}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-1 ml-2">
                  {view === 'chat' && (
                    <>
                      <button
                        onClick={clearConversation}
                        className="w-8 h-8 rounded-full hover:bg-white/20 flex items-center justify-center transition-colors"
                        title="Clear chat history"
                      >
                        <Trash2 size={14} className="text-white" />
                      </button>
                      <button
                        onClick={() => setView('settings')}
                        className="w-8 h-8 rounded-full hover:bg-white/20 flex items-center justify-center transition-colors"
                        title="Configure AI Session"
                      >
                        <Settings size={15} className="text-white" />
                      </button>
                    </>
                  )}
                  <button
                    onClick={() => setIsMaximized(!isMaximized)}
                    className="hidden sm:flex w-8 h-8 rounded-full hover:bg-white/20 items-center justify-center transition-colors"
                    title={isMaximized ? "Minimize" : "Maximize"}
                  >
                    {isMaximized ? <Minimize2 size={15} className="text-white" /> : <Maximize2 size={15} className="text-white" />}
                  </button>
                  <button
                    onClick={() => { setIsOpen(false); setIsMaximized(false); }}
                    className="w-8 h-8 rounded-full hover:bg-white/20 flex items-center justify-center transition-colors ml-1 bg-black/10"
                    title="Close widget"
                  >
                    <X size={16} className="text-white" />
                  </button>
                </div>
              </div>

              {/* View Switcher */}
              {view === 'settings' ? (
                <ChatSettingsView sessionId={sessionId} onBack={() => setView('chat')} />
              ) : (
                <>
                  {/* Messages Area */}
                  <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5 bg-slate-50/50 scroll-smooth">
                    {messages.length === 0 && (
                      <div className="flex flex-col items-center justify-center h-full text-center px-4 py-8">
                        <div className="w-16 h-16 bg-gradient-to-br from-teal-100 to-cyan-100 rounded-2xl flex items-center justify-center mb-4 shadow-sm border border-cyan-200/50">
                          <Bot size={28} className="text-cyan-600" />
                        </div>
                        <p className="font-bold text-gray-800 text-lg">Welcome to TrustFin</p>
                        <p className="text-sm text-gray-500 mt-2 max-w-[240px] leading-relaxed">
                          I can help you check loan eligibility, track applications, or explain our financial products.
                        </p>
                        <div className="mt-6 flex flex-col sm:flex-row flex-wrap justify-center gap-2 w-full max-w-lg">
                          {["What are your home loan rates?", "I need help with my EMI", "Documents required for a business loan?"].map(q => (
                            <button key={q} onClick={() => handleFollowUp(q)} className="text-xs bg-white border border-gray-200 hover:border-cyan-300 hover:bg-cyan-50 text-gray-600 py-2.5 px-3 rounded-xl transition-all shadow-sm text-left">
                              {q}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {messages.map((msg) => (
                      <ChatMessage key={msg.id} message={msg} />
                    ))}

                    {/* Streaming Indicator */}
                    {isStreaming && messages[messages.length - 1]?.role === 'user' && (
                      <div className="flex gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0 shadow-sm">
                          <Bot size={14} className="text-white" />
                        </div>
                        <div className="px-4 py-3 bg-white border border-gray-200 rounded-2xl rounded-tl-sm shadow-sm">
                          <div className="flex gap-1.5 items-center h-4">
                            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:0ms]" />
                            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:150ms]" />
                            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:300ms]" />
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Error State */}
                    {error && (
                      <div className="flex items-center gap-2 text-xs text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3 shadow-sm animate-in fade-in">
                        <AlertTriangle size={14} className="shrink-0" />
                        <p>{error}</p>
                      </div>
                    )}

                    {/* Follow-up suggestions */}
                    {!isStreaming && followUps.length > 0 && (
                      <div className="flex flex-wrap gap-2 pt-2">
                        {followUps.map((fu, i) => (
                          <button
                            key={i}
                            onClick={() => handleFollowUp(fu)}
                            className="text-xs px-3.5 py-2 rounded-xl border border-teal-200 bg-teal-50 text-teal-700 hover:bg-teal-100 transition-colors text-left shadow-sm font-medium"
                          >
                            {fu}
                          </button>
                        ))}
                      </div>
                    )}

                    <div ref={messagesEndRef} className="h-2" />
                  </div>

                  {/* Input Area */}
                  <ChatInput
                    value={input}
                    onChange={setInput}
                    onSend={handleSend}
                    onStop={stopGeneration}
                    isStreaming={isStreaming}
                  />
                </>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* FAB (Floating Action Button) - Hidden when maximized or open */}
      {!isOpen && (
        <motion.button
          whileHover={{ scale: 1.05, y: -2 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => setIsOpen((p) => !p)}
          className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-2xl flex items-center justify-center text-white transition-all border border-white/20 bg-gradient-to-br from-cyan-500 to-teal-600"
          aria-label="Open chat"
        >
          <AnimatePresence mode="wait">
            {isOpen ? (
              <motion.span key="x" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.15 }}>
                <X size={24} />
              </motion.span>
            ) : (
              <motion.span key="chat" initial={{ scale: 0.5, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.5, opacity: 0 }} transition={{ duration: 0.15 }}>
                <MessageCircle size={24} />
              </motion.span>
            )}
          </AnimatePresence>

          {!isOpen && messages.length > 0 && (
            <span className="absolute top-0 right-0 w-3.5 h-3.5 bg-red-500 rounded-full border-2 border-white animate-pulse" />
          )}
        </motion.button>
      )}
    </>
  )
}