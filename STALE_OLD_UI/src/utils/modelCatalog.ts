import type { Provider, ProviderCategory, Model, ParameterSpec } from '../types/chat';

export function filterModelsByParam(
  categories: ProviderCategory[],
  targetParam: string,
): ProviderCategory[] {
  return (categories ?? [])
    .map((category) => ({
      ...category,
      models: (category.models ?? []).filter((model) =>
        Array.isArray(model.supportedParameters) &&
        model.supportedParameters.includes(targetParam),
      ),
    }))
    .filter((category) => (category.models ?? []).length > 0);
}

export function flattenCategories(categories: ProviderCategory[]): Model[] {
  const out: Model[] = [];
  for (const c of categories ?? []) for (const m of c.models ?? []) out.push(m);
  return out;
}

function num(v: unknown): number | undefined {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string') {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return undefined;
}

function normalizePricing(raw: any): Model['pricing'] | undefined {
  const p = num(raw?.prompt);
  const c = num(raw?.completion);
  if (p == null || c == null) return undefined;
  if (p < 0 || c < 0) return undefined;

  return {
    prompt: p,
    completion: c,
    unit: raw?.unit ? String(raw.unit) : undefined
  };
}

function normalizeParameterSpecs(raw: any): ParameterSpec[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(Boolean)
    .map((ps: any): ParameterSpec => ({
      name: String(ps?.name ?? ''),
      type: ps?.type ? String(ps.type) : undefined,
      options: Array.isArray(ps?.options) ? ps.options.map(String) : null,
      default: ps?.default != null ? String(ps.default) : undefined,
      min: num(ps?.min),
      max: num(ps?.max),
    }))
    .filter((ps: ParameterSpec) => ps.name.length > 0);
}

function inferVendorFromId(id: string): string | undefined {
  const idx = id.indexOf('/');
  if (idx > 0) return id.slice(0, idx);
  return undefined;
}

// --- HELPER TO PARSE A SINGLE MODEL OBJECT ---
function parseModel(m: any, provider: Provider, vendor: string): Model | null {
  if (!m || !m.id) return null;

  const id = String(m.id);
  const name = m.name != null ? String(m.name) : undefined;

  const modality = m.modality != null ? String(m.modality) : undefined;
  const type = m.type != null ? String(m.type) : undefined;

  const contextLength = num(m.contextLength);
  const architecture = m.architecture ?? undefined;

  const parameterSpecs = normalizeParameterSpecs(m.parameterSpecs);

  // Use explicit supportedParameters if available, otherwise derive from specs
  const supportedParameters = Array.isArray(m.supportedParameters)
    ? m.supportedParameters.map(String)
    : parameterSpecs.map((ps) => ps.name);

  return {
    id,
    name,
    modality,
    type,
    architecture,
    contextLength,
    provider,
    vendor,
    pricing: normalizePricing(m.pricing),
    parameterSpecs,
    supportedParameters,
  };
}

export function normalizeCategories(raw: any, provider: Provider): ProviderCategory[] {
  const rootResponse = raw?.data?.models?.[0] ?? raw?.models?.[0];
  if (!rootResponse) return [];

  const normModels: Model[] = [];

  // STRATEGY A: Nested Providers (OpenRouter)
  if (Array.isArray(rootResponse.providers) && rootResponse.providers.length > 0) {
    for (const subProvider of rootResponse.providers) {
      const vendorName = String(subProvider?.id ?? 'other');
      const subModels = Array.isArray(subProvider.models) ? subProvider.models : [];
      for (const m of subModels) {
        const parsed = parseModel(m, provider, vendorName);
        if (parsed) normModels.push(parsed);
      }
    }
  }
  // STRATEGY B: Flat models (Groq/NVIDIA)
  else if (Array.isArray(rootResponse.models)) {
    for (const m of rootResponse.models) {
      const vendorName = inferVendorFromId(String(m?.id ?? '')) ?? provider;
      const parsed = parseModel(m, provider, vendorName);
      if (parsed) normModels.push(parsed);
    }
  }

  return [{ name: provider, models: normModels }];
}

export function supportsParam(
  model: { supportedParameters?: string[] } | undefined,
  param: string,
) {
  return !!model?.supportedParameters?.includes(param);
}

export function getParamOptions(
  model: { parameterSpecs?: ParameterSpec[] } | undefined,
  param: string,
) {
  const specs = model?.parameterSpecs ?? [];
  const hit = specs.find((s) => s.name === param);
  return hit ? (Array.isArray(hit.options) ? hit.options : null) : null;
}

export function isReasoningCapable(
  model: { supportedParameters?: string[]; type?: string } | undefined,
): boolean {
  const sp = model?.supportedParameters ?? [];
  const t = (model?.type ?? '').toLowerCase();

  // NEW: trust server classification too
  if (t === 'reasoning') return true;

  return (
    sp.includes('reasoning') ||
    sp.includes('include_reasoning') ||
    sp.includes('reasoning_effort') ||
    sp.includes('reasoning_format')
  );
}

export function isToolCallingCapable(
  model: { supportedParameters?: string[] } | undefined,
): boolean {
  const sp = model?.supportedParameters ?? [];
  return sp.includes('tool_calling_enabled') || sp.includes('tool_choice');
}
