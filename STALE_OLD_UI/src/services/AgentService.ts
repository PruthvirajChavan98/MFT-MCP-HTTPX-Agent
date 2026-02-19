import { api } from '../lib/api';
import { SSESubscription, SSECallback } from '../lib/sse';
import type { SessionConfig, Model, ProviderCategory } from '../types/domain';

class AgentService {
  streamChat(
    sessionId: string,
    question: string,
    history: any[],
    keys: { openrouter?: string; nvidia?: string; groq?: string },
    callbacks: {
      onEvent: SSECallback;
      onDone: () => void;
      onError: (err: Error) => void;
    }
  ): SSESubscription {
    const payload = {
      session_id: sessionId,
      question,
      history,
      openrouter_api_key: keys.openrouter,
      nvidia_api_key: keys.nvidia,
      groq_api_key: keys.groq,
    };

    const sub = new SSESubscription(
      '/stream',
      payload,
      callbacks.onEvent,
      callbacks.onDone,
      callbacks.onError
    );

    sub.start();
    return sub;
  }

  async getSessionConfig(sessionId: string): Promise<SessionConfig> {
    return api.get<SessionConfig>(`/config/${sessionId}`);
  }

  async updateSessionConfig(config: SessionConfig): Promise<void> {
    return api.post('/config', config);
  }

  async getModels(): Promise<Model[]> {
    const query = `
      query {
        models {
          name
          models {
            id
            name
            provider
            contextLength
            pricing { prompt completion unit }
            supportedParameters
            parameterSpecs { name type options default min max }
          }
        }
      }
    `;

    try {
      // We hit the graphql endpoint directly via POST
      // Type is loose here to catch potential structure mismatch
      const res = await api.post<any>('/../graphql', { query });

      // ✅ FIX: Strict null checking prevents the crash
      if (!res || !res.data || !Array.isArray(res.data.models)) {
        console.warn("AgentService: Backend returned invalid model data.", res);
        return [];
      }

      // Flatten the categories
      const categories = res.data.models as ProviderCategory[];
      return categories.flatMap(cat => Array.isArray(cat.models) ? cat.models : []);

    } catch (e) {
      console.error("AgentService: Failed to fetch models", e);
      return []; // Return empty list on network failure
    }
  }

  async logout(sessionId: string): Promise<void> {
    await api.delete(`/logout/${sessionId}`);
  }
}

export const agentService = new AgentService();
