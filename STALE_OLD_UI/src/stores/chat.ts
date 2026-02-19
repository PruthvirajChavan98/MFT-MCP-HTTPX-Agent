import { createStore, produce } from 'solid-js/store';
import type { Message, Role, FollowUpCandidate, RouterEvent } from '../types/domain';
import { sessionState } from './sessionStore';

const WELCOME_MESSAGE: Message = {
  id: 'welcome-msg',
  role: 'assistant',
  content:
    "Hello! 👋 I'm your **Mock AI** assistant.\n\nI can stream my **thought process** (reasoning) separately from my final answer. Configure my model and settings in the sidebar to get started!\n\nYou can ask me any queries about loans.",
  reasoning: 'I am initialized and ready to help.',
  timestamp: Date.now(),
  isStreaming: false,
  followUpCandidates: [
    { id: 0, question: 'Check my loan eligibility', why: 'Next step to assess qualification quickly.', whyDone: true },
    { id: 1, question: 'How to pay EMI?', why: 'Common action after understanding your loan.', whyDone: true },
    { id: 2, question: 'Contact customer care', why: 'Useful if you need help immediately.', whyDone: true },
  ],
};

interface ChatState {
  messages: Message[];
  isGenerating: boolean;
  input: string;
}

const [chatState, setChatState] = createStore<ChatState>({
  messages: [WELCOME_MESSAGE],
  isGenerating: false,
  input: '',
});

export const chatActions = {
  setInput: (value: string) => setChatState('input', value),

  addMessage: (role: Role, content: string = '') => {
    const id = crypto.randomUUID();
    const message: Message = {
      id,
      role,
      content,
      reasoning: '',
      timestamp: Date.now(),
      isStreaming: true,
      followUpCandidates: [],
    };

    setChatState('messages', (msgs) => [...msgs, message]);
    if (role === 'user') setChatState('isGenerating', true);
    return id;
  },

  // Optimized updater for high-frequency SSE events
  updateMessage: (
    id: string,
    payload: {
      content?: string;
      reasoning?: string;
      router?: RouterEvent;
      followUps?: FollowUpCandidate[];
      isStreaming?: boolean;
    }
  ) => {
    setChatState(
      'messages',
      (msg) => msg.id === id,
      produce((msg) => {
        if (payload.content) msg.content += payload.content;

        // Router events replace the previous state (latest is truth)
        if (payload.router) msg.router = payload.router;

        if (payload.reasoning) {
           // Append reasoning
           msg.reasoning = (msg.reasoning || '') + payload.reasoning;
        }

        if (payload.followUps) msg.followUpCandidates = payload.followUps;

        if (payload.isStreaming !== undefined) msg.isStreaming = payload.isStreaming;
      })
    );
  },

  reset: () => {
    setChatState('messages', [WELCOME_MESSAGE]);
    setChatState('isGenerating', false);
  },
};

export { chatState };
