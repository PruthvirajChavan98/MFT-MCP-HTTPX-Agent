import { A } from '@solidjs/router'
import { Brain, ShieldCheck } from 'lucide-solid'
import ChatPanel from '../../features/chat/ChatPanel'
import { useChatController } from '../../features/chat/useChatController'
import BrainIcon from '../../shared/ui/BrainIcon'

export default function ChatPage() {
  const chat = useChatController()

  return (
    <main class="page-shell px-4 py-6 sm:px-6 lg:px-10">
      <div class="mx-auto grid w-full max-w-[1240px] gap-6 lg:grid-cols-[1fr_420px]">
        <section class="rounded-2xl border border-cyan-100 bg-white/90 p-6 shadow-[0_22px_50px_rgba(2,132,199,0.10)]">
          <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
            <div class="flex items-center gap-4">
              <BrainIcon size={72} />
              <div>
                <h1 class="text-3xl font-bold tracking-tight text-slate-900">NBFC Assistant Console</h1>
                <p class="mt-1 text-sm text-slate-600">SolidJS production UI over live agent streaming APIs.</p>
              </div>
            </div>

            <A
              href="/admin"
              class="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:border-cyan-300 hover:text-cyan-700"
            >
              <ShieldCheck size={16} />
              Open Admin
            </A>
          </div>

          <ChatPanel
            sessionId={chat.sessionId()}
            messages={chat.messages()}
            input={chat.input()}
            isStreaming={chat.isStreaming()}
            error={chat.error()}
            followUps={chat.followUps()}
            onInput={chat.setInput}
            onSend={() => void chat.sendMessage()}
            onStop={chat.stopGeneration}
            onClear={chat.clearConversation}
            onFollowUp={(question) => void chat.sendMessage(question)}
          />
        </section>

        <aside class="space-y-4">
          <div class="kpi-card">
            <div class="mb-2 inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Brain size={16} />
              Production Notes
            </div>
            <ul class="space-y-2 text-sm text-slate-600">
              <li>Uses `/agent/stream` SSE for token, reasoning, tool call and cost events.</li>
              <li>Uses `/agent/follow-up-stream` with indexed token chunks for follow-up chips.</li>
              <li>Falls back to `/agent/query` if a stream exits without any token.</li>
              <li>Session and message history persist locally for continuity across reloads.</li>
            </ul>
          </div>

          <div class="kpi-card">
            <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">Status</p>
            <p class="mt-2 text-sm text-slate-700">
              {chat.isStreaming() ? 'Streaming response from backend...' : 'Ready'}
            </p>
          </div>
        </aside>
      </div>
    </main>
  )
}
