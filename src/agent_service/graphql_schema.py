import strawberry
from typing import Dict, List, Optional, Tuple

from .model_service import model_service


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


@strawberry.type
class SubProviderCategory:
    """
    Nested provider buckets inside OpenRouter, derived from model id prefix.
    Example:
      id="openai", name="OpenAI"
      id="anthropic", name="Anthropic"
    """
    id: str
    name: str
    models: List[Model]


@strawberry.type
class ProviderCategory:
    name: str  # "groq" | "openrouter"
    models: List[Model]
    # Only populated for openrouter
    providers: Optional[List[SubProviderCategory]] = None


VALID_PROVIDERS = {"groq", "openrouter"}
REASONING_KEYS = {"reasoning", "reasoning_effort", "include_reasoning"}


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


_VENDOR_DISPLAY: Dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "meta-llama": "Meta Llama",
    "mistralai": "Mistral",
    "deepseek": "DeepSeek",
    "qwen": "Qwen",
    "cohere": "Cohere",
    "x-ai": "xAI",
    "perplexity": "Perplexity",
    "amazon": "Amazon",
    "microsoft": "Microsoft",
    "alibaba": "Alibaba",
    "other": "Other",
}


def _humanize_slug(slug: str) -> str:
    """
    Makes `gpt-4o-mini` -> `GPT 4o mini` (good enough for sorting + UI).
    We keep it intentionally simple and safe.
    """
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

        # 70b -> 70B
        if pl.endswith("b") and pl[:-1].isdigit():
            out.append(pl[:-1] + "B")
            continue

        # Keep o1/o3 as-is (OpenAI naming)
        if pl in {"o1", "o3"}:
            out.append(pl)
            continue

        # Default: keep original token
        out.append(p)

    return " ".join(out).strip() or (slug or "").strip()


def derive_display_name(model_id: str, provider: str, api_name: Optional[str]) -> str:
    """
    If OpenRouter gives a good name, use it.
    If it's missing or basically equals the id, derive a readable display name.
    """
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

    # groq legacy ids sometimes have no slash
    return nm or mid


def _model_sort_key(m: Model) -> Tuple[str, str]:
    return ((m.name or "").casefold(), (m.id or "").casefold())


@strawberry.type
class Query:
    @strawberry.field
    async def models(
        self,
        is_reasoning: Optional[bool] = None,
        provider: Optional[str] = None,
    ) -> List[ProviderCategory]:
        """
        Providers are ONLY:
          - "groq"
          - "openrouter"

        Behavior:
          - provider=None            -> returns both (if they exist in cache)
          - provider="groq"          -> returns only groq bucket
          - provider="openrouter"    -> returns only openrouter bucket

        Notes:
          - Output is sorted by derived display name.
          - openrouter additionally includes nested `providers` buckets (openai, anthropic, etc).
        """
        if provider is not None:
            provider = (provider or "").strip().lower()
            if provider and provider not in VALID_PROVIDERS:
                raise ValueError(f"Invalid provider: {provider}. Use 'groq' or 'openrouter'.")

        all_data = await model_service.get_cached_data()
        by_bucket = {c.get("name"): c for c in (all_data or []) if isinstance(c, dict)}

        names = [provider] if provider else ["groq", "openrouter"]

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

                supported = set(m.get("supported_parameters", []) or [])
                is_reasoning_model = bool(REASONING_KEYS.intersection(supported))

                if is_reasoning is not None:
                    if is_reasoning and not is_reasoning_model:
                        continue
                    if (not is_reasoning) and is_reasoning_model:
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
                        supported_parameters=list(m.get("supported_parameters", []) or []),
                        parameter_specs=specs,
                    )
                )

            # Sort flat list always (so your UI "sort by name" works immediately)
            filtered_models.sort(key=_model_sort_key)

            # Build nested providers only for openrouter
            providers: Optional[List[SubProviderCategory]] = None
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
                providers = provider_objs

            # Bucket inclusion rules (same spirit as your old code)
            if provider:
                categories.append(ProviderCategory(name=cat_name, models=filtered_models, providers=providers))
            else:
                # skip empty buckets to keep payload small
                if filtered_models:
                    categories.append(ProviderCategory(name=cat_name, models=filtered_models, providers=providers))

        return categories


schema = strawberry.Schema(query=Query)
