// --- Enums ---
export type Provider = 'groq' | 'openrouter' | 'nvidia';
export type Role = 'user' | 'assistant';

// --- Chat Models ---
export interface Message {
  id: string;
  role: Role;
  content: string;
  reasoning?: string;
  timestamp: number;
  isStreaming?: boolean;
  followUpCandidates?: FollowUpCandidate[];
  router?: RouterEvent;
  routerEvents?: RouterEvent[];
}

export interface FollowUpCandidate {
  id: number;
  question: string;
  why?: string;
  whyDone?: boolean;
}

// --- Router Models ---
export interface RouterLabelScore {
  label?: string;
  score?: number;
  top?: Array<[string, number]>;
  override?: boolean | string;
  override_reason?: string | null;
}

export interface RouterBackendResult {
  backend: string;
  sentiment?: RouterLabelScore;
  reason?: RouterLabelScore;
  meta?: any;
}

export interface RouterEvent {
  mode?: string;
  chosen_backend?: string;
  results: RouterBackendResult[];
  raw?: any;
}

// --- Configuration Models ---
export interface SessionConfig {
  session_id: string;
  system_prompt?: string;
  model_name?: string;
  provider?: Provider;
  reasoning_effort?: string | null;

  has_openrouter_key?: boolean;
  has_nvidia_key?: boolean;
  has_groq_key?: boolean;
  has_custom_key?: boolean;

  openrouter_api_key?: string;
  nvidia_api_key?: string;
  groq_api_key?: string;
}

// --- Model Catalog Types ---
export interface ParameterSpec {
  name: string;
  type?: string;
  options: string[] | null;
  default?: string | null;
  min?: number;
  max?: number;
}

export interface Pricing {
  prompt: number;
  completion: number;
  unit?: string;
}

export interface Model {
  id: string;
  name?: string;
  provider: Provider;
  vendor?: string;
  contextLength?: number;
  pricing?: Pricing;
  parameterSpecs: ParameterSpec[];
  supportedParameters: string[];

  // ✅ ADDED THESE MISSING FIELDS
  modality?: string;
  type?: string;
  architecture?: any;
}

export interface ProviderCategory {
  name: string;
  models: Model[];
}

// --- Evaluation Models ---
export interface EvalTrace {
  trace_id: string;
  session_id: string | null;
  status: string | null;
  latency_ms: number | null;
  model: string | null;
  event_count: number;
  router_sentiment?: string | null;
  router_reason?: string | null;
}
