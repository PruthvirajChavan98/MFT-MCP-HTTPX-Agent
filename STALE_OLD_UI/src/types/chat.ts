// Compatibility shim for legacy components
import type { Model, ParameterSpec, Provider, SessionConfig, FollowUpCandidate, RouterEvent } from './domain';

export type { Model, ParameterSpec, Provider, SessionConfig, FollowUpCandidate, RouterEvent };

export interface ProviderCategory {
  name: string;
  models: Model[];
}

export type Role = 'user' | 'assistant';

export interface Message {
  id: string;
  role: Role;
  content: string;
  reasoning?: string;
  timestamp: number;
  isStreaming?: boolean;
  followUpCandidates?: FollowUpCandidate[];
  router?: RouterEvent | any;
  routerEvents?: Array<RouterEvent | any>;
}

export interface ChatState {
  sessionId: string;
  messages: Message[];
  isConnected: boolean;
  isGenerating: boolean;
  input: string;
}
