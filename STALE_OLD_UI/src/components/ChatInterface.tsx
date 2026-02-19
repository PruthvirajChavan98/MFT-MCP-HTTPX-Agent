import { Component, createEffect, createSignal, For, Show } from 'solid-js';
import { ArrowDown } from 'lucide-solid';
import { chatState, chatActions } from '../stores/chat';
import { sessionState } from '../stores/sessionStore';
import { agentService } from '../services/AgentService';
import Header from './Header';
import MessageItem from './MessageItem';
import ChatInput from './ChatInput';

const ChatInterface: Component = () => {
  let scrollRef: HTMLDivElement | undefined;
  const [userScrolledUp, setUserScrolledUp] = createSignal(false);
  const [streamError, setStreamError] = createSignal<string | null>(null);

  // Auto-scroll logic
  const scrollToBottom = () => {
    if (scrollRef) {
      scrollRef.scrollTo({ top: scrollRef.scrollHeight, behavior: 'smooth' });
      setUserScrolledUp(false);
    }
  };

  const handleScroll = () => {
    if (!scrollRef) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef;
    // Tolerance of 100px
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 100;
    setUserScrolledUp(!isAtBottom);
  };

  // Effect: Scroll on new messages unless user looked up
  createEffect(() => {
    chatState.messages.length; // dependency
    if (!userScrolledUp()) scrollToBottom();
  });

  const handleSubmit = async (text: string) => {
    if (!text.trim() || chatState.isGenerating) return;

    setStreamError(null);
    chatActions.setInput('');

    // 1. Add User Message
    chatActions.addMessage('user', text);

    // 2. Add Assistant Placeholder
    const aiMsgId = chatActions.addMessage('assistant', '');

    // 3. Prepare History (exclude the just-added placeholders)
    const history = chatState.messages.slice(0, -2).map(m => ({
      role: m.role,
      content: m.content
    }));

    // 4. Start Stream
    agentService.streamChat(
      sessionState.sessionId,
      text,
      history,
      sessionState.keys,
      {
        onEvent: (event, data) => {
          if (event === 'token') {
            chatActions.updateMessage(aiMsgId, { content: data });
          } else if (event === 'reasoning_token') {
            chatActions.updateMessage(aiMsgId, { reasoning: data });
          } else if (event === 'router') {
            try {
              chatActions.updateMessage(aiMsgId, { router: JSON.parse(data) });
            } catch {}
          } else if (event === 'tool_start') {
             try {
               const tool = JSON.parse(data);
               chatActions.updateMessage(aiMsgId, { reasoning: `\n\n> Tool Call: ${tool.tool}\n` });
             } catch {}
          } else if (event === 'tool_end') {
             try {
               const res = JSON.parse(data);
               chatActions.updateMessage(aiMsgId, { reasoning: `\n> Result: ${res.output}\n\n` });
             } catch {}
          }
        },
        onDone: () => {
          chatActions.updateMessage(aiMsgId, { isStreaming: false });
          chatState.isGenerating = false; // direct mutation allowed via store
        },
        onError: (err) => {
          setStreamError(err.message);
          chatActions.updateMessage(aiMsgId, { content: `\n\n**Error:** ${err.message}`, isStreaming: false });
          chatState.isGenerating = false;
        }
      }
    );
  };

  return (
    <div class="flex h-full w-full flex-col">
      <Header />

      <main class="relative flex-1 overflow-hidden bg-slate-50/50 dark:bg-slate-950/50">
        <div
          ref={(el) => (scrollRef = el)}
          onScroll={handleScroll}
          class="h-full overflow-y-auto scroll-smooth px-4 pt-6 pb-4 no-scrollbar"
        >
          <div class="mx-auto max-w-4xl space-y-6 pb-4">
            <For each={chatState.messages}>
              {(msg) => (
                <MessageItem
                  message={msg}
                  isGenerating={chatState.isGenerating}
                  onFollowUpClick={handleSubmit}
                />
              )}
            </For>
            <div class="h-24" /> {/* Spacer for Input */}
          </div>
        </div>

        <Show when={userScrolledUp()}>
          <button
            onClick={scrollToBottom}
            class="absolute bottom-6 right-1/2 translate-x-1/2 z-20 flex items-center gap-2 rounded-full bg-slate-900/90 px-4 py-2 text-xs font-semibold text-white shadow-xl backdrop-blur-sm hover:bg-slate-800 transition-all animate-bounce"
          >
            <ArrowDown size={14} /> <span>New messages</span>
          </button>
        </Show>
      </main>

      <ChatInput onSend={handleSubmit} error={streamError()} />
    </div>
  );
};

export default ChatInterface;
