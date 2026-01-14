import strawberry
from strawberry.scalars import JSON
from typing import Dict, List, Optional, Tuple, Iterable, Set, Any

# Updated import path to llm.catalog
from src.agent_service.llm.catalog import model_service

@strawberry.type
class ParameterSpec:
    name: str
    type: str  # "enum", "boolean", "float", "int"
    options: Optional[List[str]] = None
    default: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None

@strawberry.type
class ModelPricing:
    prompt: float
    completion: float
    unit: str

@strawberry.type
class Model:
    id: str
    name: str
    context_length: int
    pricing: ModelPricing
    supported_parameters: List[str]
    parameter_specs: List[ParameterSpec]
    # NEW: classification + architecture passthrough
    modality: Optional[str] = None         # "text" | "vision" | "embedding"
    type: Optional[str] = None             # "chat" | "instruct" | "code" | "reasoning" | ...
    architecture: Optional[JSON] = None    # OpenRouter architecture blob (if present)

@strawberry.type
class SubProviderCategory:
    id: str
    name: str
    models: List[Model]

@strawberry.type
class ProviderCategory:
    name: str  # "groq" | "nvidia" | "openrouter"
    models: List[Model]
    providers: Optional[List[SubProviderCategory]] = None

VALID_PROVIDERS = {"groq", "nvidia", "openrouter"}
REASONING_KEYS = {"reasoning", "reasoning_effort", "include_reasoning"}

_VENDOR_DISPLAY: Dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "meta-llama": "Meta Llama",
    "mistralai": "Mistral",
    "deepseek": "DeepSeek",
    "deepseek-ai": "DeepSeek",
    "qwen": "Qwen",
    "cohere": "Cohere",
    "x-ai": "xAI",
    "perplexity": "Perplexity",
    "amazon": "Amazon",
    "microsoft": "Microsoft",
    "alibaba": "Alibaba",
    "nvidia": "NVIDIA",
    "01-ai": "01.AI",
    "other": "Other",
}

def _to_float(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0

def _vendor_from_id(model_id: str) -> str:
    s = (model_id or "").strip()
    if "/" in s:
        return s.split("/", 1)[0].strip().lower() or "other"
    return "other"

def _humanize_slug(slug: str) -> str:
    raw = (slug or "").strip().replace("_", "-")
    parts = [p for p in raw.split("-") if p]

    token_map = {
        "gpt": "GPT",
        "llama": "Llama",
        "claude": "Claude",
        "gemini": "Gemini",
        "deepseek": "DeepSeek",
        "qwen": "Qwen",
        "mixtral": "Mixtral",
        "r1": "R1",
    }

    out: List[str] = []
    for p in parts:
        pl = p.lower()

        if pl in token_map:
            out.append(token_map[pl])
            continue
        if pl.endswith("b") and pl[:-1].isdigit():
            out.append(pl[:-1] + "B")
            continue
        if pl in {"o1", "o3"}:
            out.append(pl)
            continue
        out.append(p)

    return " ".join(out).strip() or (slug or "").strip()

def derive_display_name(model_id: str, provider: str, api_name: Optional[str]) -> str:
    mid = (model_id or "").strip()
    nm = (api_name or "").strip()

    if nm and nm.casefold() != mid.casefold():
        return nm

    if "/" in mid:
        vendor, slug = mid.split("/", 1)
        vendor_key = vendor.strip().lower() or "other"
        vendor_disp = _VENDOR_DISPLAY.get(vendor_key, vendor.replace("-", " ").title())
        slug_disp = _humanize_slug(slug)
        return f"{vendor_disp} {slug_disp}".strip()

    return nm or mid

def _model_sort_key(m: Model) -> Tuple[str, str]:
    return ((m.name or "").casefold(), (m.id or "").casefold())

def _as_set(x: Optional[Iterable[str]]) -> Optional[Set[str]]:
    if x is None:
        return None
    return {str(v).strip().lower() for v in x if str(v).strip()}

def _match_set(need: Optional[Set[str]], have: Iterable[str]) -> bool:
    if not need:
        return True
    have_set = {str(v).strip().lower() for v in (have or [])}
    return need.issubset(have_set)

def _pseudo_arch_for_non_openrouter() -> Dict[str, Any]:
    return {
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "modality": "text->text",
        "instruct_type": "",
    }

@strawberry.type
class Query:
    @strawberry.field
    async def models(
        self,
        is_reasoning: Optional[bool] = None,
        provider: Optional[str] = None,

        # NEW: cross-provider classification filters
        modalities: Optional[List[str]] = None,   # ["text","vision","embedding"]
        types: Optional[List[str]] = None,        # ["chat","instruct","code","reasoning","safety",...]

        # NEW: OpenRouter-style architecture filters (also applied to non-OR as text->text)
        input_modalities: Optional[List[str]] = None,   # ["text"], ["text","image"], ...
        output_modalities: Optional[List[str]] = None,  # ["text"], ["image"], ...
        modality: Optional[str] = None,                 # "text->text", "text+image->text"
        instruct_type: Optional[str] = None,            # "chatml", etc

        # NEW: vendor prefix filter ("openai", "anthropic", ...)
        vendor: Optional[str] = None,
    ) -> List[ProviderCategory]:
        if provider is not None:
            provider = (provider or "").strip().lower()
            if provider and provider not in VALID_PROVIDERS:
                raise ValueError("Invalid provider. Use 'groq', 'nvidia', or 'openrouter'.")

        modalities_need = _as_set(modalities)
        types_need = _as_set(types)
        in_need = _as_set(input_modalities)
        out_need = _as_set(output_modalities)
        modality_need = (modality or "").strip().lower() or None
        instruct_need = (instruct_type or "").strip().lower() or None
        vendor_need = (vendor or "").strip().lower() or None

        all_data = await model_service.get_cached_data()
        by_bucket = {c.get("name"): c for c in (all_data or []) if isinstance(c, dict)}

        names = [provider] if provider else ["groq", "nvidia", "openrouter"]
        categories: List[ProviderCategory] = []

        for cat_name in names:
            bucket = by_bucket.get(cat_name, {}) or {}
            raw_models = bucket.get("models", [])
            if not isinstance(raw_models, list):
                raw_models = []

            filtered_models: List[Model] = []

            for m in raw_models:
                if not isinstance(m, dict):
                    continue

                mid = str(m.get("id") or "").strip()
                if not mid:
                    continue

                # vendor filter
                if vendor_need and _vendor_from_id(mid) != vendor_need:
                    continue

                supported = list(m.get("supported_parameters", []) or [])
                supported_set = set(supported)
                is_reasoning_model = bool(REASONING_KEYS.intersection(supported_set))

                if is_reasoning is not None:
                    if is_reasoning and not is_reasoning_model:
                        continue
                    if (not is_reasoning) and is_reasoning_model:
                        continue

                # classification filters
                m_mod = str(m.get("modality") or "").strip().lower() or "text"
                m_type = str(m.get("type") or "").strip().lower() or "other"

                if modalities_need and m_mod not in modalities_need:
                    continue
                if types_need and m_type not in types_need:
                    continue

                # architecture filters (OpenRouter-style)
                arch = m.get("architecture") or _pseudo_arch_for_non_openrouter()
                arch_in = arch.get("input_modalities") or []
                arch_out = arch.get("output_modalities") or []
                arch_mod = str(arch.get("modality") or "").strip().lower()
                arch_type = str(arch.get("instruct_type") or "").strip().lower()

                if modality_need and arch_mod != modality_need:
                    continue
                if instruct_need and arch_type != instruct_need:
                    continue
                if not _match_set(in_need, arch_in):
                    continue
                if not _match_set(out_need, arch_out):
                    continue

                pricing_dict = m.get("pricing", {}) or {}
                pricing = ModelPricing(
                    prompt=_to_float(pricing_dict.get("prompt")),
                    completion=_to_float(pricing_dict.get("completion")),
                    unit=str(pricing_dict.get("unit") or "1M tokens"),
                )

                specs: List[ParameterSpec] = []
                for s in (m.get("parameter_specs", []) or []):
                    if not isinstance(s, dict):
                        continue
                    specs.append(
                        ParameterSpec(
                            name=str(s.get("name") or ""),
                            type=str(s.get("type") or "string"),
                            options=s.get("options"),
                            default=str(s.get("default")) if s.get("default") is not None else None,
                            min=s.get("min"),
                            max=s.get("max"),
                        )
                    )

                display_name = derive_display_name(
                    model_id=mid,
                    provider=cat_name,
                    api_name=str(m.get("name") or "").strip(),
                )

                filtered_models.append(
                    Model(
                        id=mid,
                        name=display_name,
                        context_length=int(m.get("context_length") or 0),
                        pricing=pricing,
                        supported_parameters=supported,
                        parameter_specs=specs,
                        modality=m_mod,
                        type=m_type,
                        architecture=arch if isinstance(arch, dict) else None, # type: ignore
                    )
                )

            filtered_models.sort(key=_model_sort_key)

            providers_out: Optional[List[SubProviderCategory]] = None
            if cat_name == "openrouter":
                grouped: Dict[str, List[Model]] = {}
                for mdl in filtered_models:
                    vid = _vendor_from_id(mdl.id)
                    grouped.setdefault(vid, []).append(mdl)

                provider_objs: List[SubProviderCategory] = []
                for vid, models_list in grouped.items():
                    models_list.sort(key=_model_sort_key)
                    provider_objs.append(
                        SubProviderCategory(
                            id=vid,
                            name=_VENDOR_DISPLAY.get(vid, vid.replace("-", " ").title()),
                            models=models_list,
                        )
                    )

                provider_objs.sort(key=lambda p: (p.name or "").casefold())
                providers_out = provider_objs

            if provider:
                categories.append(ProviderCategory(name=cat_name, models=filtered_models, providers=providers_out))
            else:
                if filtered_models:
                    categories.append(ProviderCategory(name=cat_name, models=filtered_models, providers=providers_out))

        return categories

schema = strawberry.Schema(query=Query)