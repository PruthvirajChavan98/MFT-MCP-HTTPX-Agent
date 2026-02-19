import { createStore } from 'solid-js/store';
import type { SessionConfig } from '../types/domain';

const SESSION_KEY = 'dual_stream_session_id';
const KEY_PREFIX = 'dual_stream_key_';

interface SessionState {
  sessionId: string;
  config: SessionConfig | null;
  keys: {
    openrouter?: string;
    nvidia?: string;
    groq?: string;
  };
}

// 1. Helper to generate UUID
const generateUUID = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

// 2. Load initial state
const loadInitialSession = (): string => {
  try {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing && existing.length >= 8) return existing;
    const fresh = generateUUID();
    localStorage.setItem(SESSION_KEY, fresh);
    return fresh;
  } catch {
    return generateUUID();
  }
};

const initialSessionId = loadInitialSession();

const [sessionState, setSessionState] = createStore<SessionState>({
  sessionId: initialSessionId,
  config: null,
  keys: {
    openrouter: localStorage.getItem(KEY_PREFIX + 'or_' + initialSessionId) || undefined,
    nvidia: localStorage.getItem(KEY_PREFIX + 'nv_' + initialSessionId) || undefined,
    groq: localStorage.getItem(KEY_PREFIX + 'gr_' + initialSessionId) || undefined,
  },
});

export const sessionActions = {
  resetSession: () => {
    const fresh = generateUUID();
    localStorage.setItem(SESSION_KEY, fresh);
    setSessionState({
      sessionId: fresh,
      config: null,
      keys: { openrouter: undefined, nvidia: undefined, groq: undefined },
    });
    // Dispatch event for other components to react
    window.dispatchEvent(new Event('session-reset'));
  },

  setConfig: (config: SessionConfig) => {
    setSessionState('config', config);
  },

  saveKeys: (keys: { openrouter?: string; nvidia?: string; groq?: string }) => {
    const sid = sessionState.sessionId;

    if (keys.openrouter) localStorage.setItem(KEY_PREFIX + 'or_' + sid, keys.openrouter);
    if (keys.nvidia) localStorage.setItem(KEY_PREFIX + 'nv_' + sid, keys.nvidia);
    if (keys.groq) localStorage.setItem(KEY_PREFIX + 'gr_' + sid, keys.groq);

    setSessionState('keys', (prev) => ({ ...prev, ...keys }));
  },

  getKeys: () => sessionState.keys,
};

export { sessionState };
