import { useState, useRef, useEffect } from 'react'
import { Bot, MessageCircle, X, Trash2 } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { useChatStream } from '../../shared/hooks/useChatStream'
import { cn } from './ui/utils'

export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { messages, followUps, isStreaming, error, sendMessage, stopGeneration, clearConversation } =
    useChatStream()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    if (isOpen) scrollToBottom()
  }, [messages, isStreaming, isOpen])

  const handleSend = () => {
    if (!input.trim() || isStreaming) return
    sendMessage(input)
    setInput('')
  }

  const handleFollowUp = (text: string) => {
    sendMessage(text)
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
      {/* Chat window */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.85, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.85, y: 20 }}
            transition={{ type: 'spring', stiffness: 350, damping: 30 }}
            className="w-[380px] max-w-[calc(100vw-2rem)] h-[540px] max-h-[calc(100vh-8rem)] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-gray-200 origin-bottom-right"
          >
            {/* Header */}
            <div className="bg-gradient-to-r from-cyan-500 to-teal-500 text-white p-4 flex items-center gap-3 flex-shrink-0">
              <div className="w-9 h-9 bg-white/20 rounded-full flex items-center justify-center">
                <Bot size={18} className="text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-sm leading-tight">TrustFin Assistant</h3>
                <p className="text-white/80 text-xs flex items-center gap-1.5 mt-0.5">
                  <span className={cn('w-1.5 h-1.5 rounded-full', isStreaming ? 'bg-yellow-300 animate-pulse' : 'bg-green-400')} />
                  {isStreaming ? 'Thinking…' : 'Online'}
                </p>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={clearConversation}
                  className="w-7 h-7 rounded-full hover:bg-white/20 flex items-center justify-center transition-colors"
                  title="Clear chat"
                >
                  <Trash2 size={13} className="text-white" />
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  className="w-7 h-7 rounded-full hover:bg-white/20 flex items-center justify-center transition-colors"
                >
                  <X size={15} className="text-white" />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50/40">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-center gap-3 py-8">
                  <div className="w-12 h-12 bg-cyan-100 rounded-full flex items-center justify-center">
                    <Bot size={22} className="text-cyan-600" />
                  </div>
                  <div>
                    <p className="font-medium text-sm text-gray-700">Welcome to TrustFin</p>
                    <p className="text-xs text-gray-500 mt-1 max-w-[220px]">
                      Ask me about home loans, business loans, EMI schedules, and more.
                    </p>
                  </div>
                </div>
              )}

              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}

              {/* Streaming dot indicator */}
              {isStreaming && messages[messages.length - 1]?.role === 'user' && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center flex-shrink-0">
                    <Bot size={14} className="text-white" />
                  </div>
                  <div className="px-4 py-3 bg-white border border-gray-100 rounded-2xl rounded-tl-sm shadow-sm">
                    <div className="flex gap-1 items-center h-4">
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:0ms]" />
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:150ms]" />
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:300ms]" />
                    </div>
                  </div>
                </div>
              )}

              {/* Error */}
              {error && (
                <p className="text-xs text-red-500 text-center bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              {/* Follow-up suggestions */}
              {!isStreaming && followUps.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {followUps.map((fu, i) => (
                    <button
                      key={i}
                      onClick={() => handleFollowUp(fu)}
                      className="text-xs px-3 py-1.5 rounded-full border border-cyan-200 bg-cyan-50 text-cyan-700 hover:bg-cyan-100 transition-colors text-left"
                    >
                      {fu}
                    </button>
                  ))}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <ChatInput
              value={input}
              onChange={setInput}
              onSend={handleSend}
              onStop={stopGeneration}
              isStreaming={isStreaming}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* FAB */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setIsOpen((p) => !p)}
        className="w-14 h-14 rounded-full bg-gradient-to-br from-cyan-500 to-teal-600 shadow-lg hover:shadow-xl flex items-center justify-center text-white transition-shadow"
        aria-label="Open chat"
      >
        <AnimatePresence mode="wait">
          {isOpen ? (
            <motion.span key="x" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.15 }}>
              <X size={22} />
            </motion.span>
          ) : (
            <motion.span key="chat" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }} transition={{ duration: 0.15 }}>
              <MessageCircle size={22} />
            </motion.span>
          )}
        </AnimatePresence>
        {/* Unread dot when closed */}
        {!isOpen && messages.length > 0 && (
          <span className="absolute top-0 right-0 w-3 h-3 bg-red-500 rounded-full border-2 border-white" />
        )}
      </motion.button>
    </div>
  )
}
