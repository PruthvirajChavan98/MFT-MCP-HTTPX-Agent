from typing import List, Optional

import strawberry
from strawberry.scalars import JSON

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
    # ✅ FIX: Expose provider field to frontend
    provider: str
    context_length: int
    pricing: ModelPricing
    supported_parameters: List[str]
    parameter_specs: List[ParameterSpec]
    modality: Optional[str] = None
    type: Optional[str] = None
    architecture: Optional[JSON] = None


@strawberry.type
class SubProviderCategory:
    id: str
    name: str
    models: List[Model]


@strawberry.type
class ProviderCategory:
    name: str
    models: List[Model]
    providers: Optional[List[SubProviderCategory]] = None


VALID_PROVIDERS = {"groq", "nvidia", "openrouter"}
REASONING_KEYS = {"reasoning", "reasoning_effort", "include_reasoning"}


def _to_float(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


@strawberry.type
class Query:
    @strawberry.field
    async def models(
        self,
        provider: Optional[str] = None,
    ) -> List[ProviderCategory]:
        # Fetch all raw data from catalog service
        all_data = await model_service.get_cached_data()

        # Convert raw dicts to Strawberry Types
        categories = []
        for cat in all_data:
            cat_name = cat.get("name")

            # Filter if provider arg is present
            if provider and cat_name != provider:
                continue

            raw_models = cat.get("models", [])
            typed_models = []

            for m in raw_models:
                # Safe Parsing
                pricing_dict = m.get("pricing", {}) or {}
                pricing = ModelPricing(
                    prompt=_to_float(pricing_dict.get("prompt")),
                    completion=_to_float(pricing_dict.get("completion")),
                    unit=str(pricing_dict.get("unit") or "1M tokens"),
                )

                specs = []
                for s in m.get("parameter_specs", []) or []:
                    specs.append(
                        ParameterSpec(
                            name=s.get("name", ""),
                            type=s.get("type", "string"),
                            options=s.get("options"),
                            default=str(s.get("default")) if s.get("default") is not None else None,
                            min=s.get("min"),
                            max=s.get("max"),
                        )
                    )

                typed_models.append(
                    Model(
                        id=m.get("id", ""),
                        name=m.get("name", ""),
                        provider=m.get("provider", cat_name),  # ✅ FIX: Map provider
                        context_length=int(m.get("context_length") or 0),
                        pricing=pricing,
                        supported_parameters=m.get("supported_parameters", []),
                        parameter_specs=specs,
                        modality=m.get("modality"),
                        type=m.get("type"),
                        architecture=m.get("architecture"),
                    )
                )

            categories.append(ProviderCategory(name=cat_name, models=typed_models))

        return categories


schema = strawberry.Schema(query=Query)
