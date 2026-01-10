import strawberry
from typing import List, Optional
from .model_service import model_service

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

@strawberry.type
class ProviderCategory:
    name: str
    models: List[Model]

@strawberry.type
class Query:
    @strawberry.field
    async def models(self, is_reasoning: Optional[bool] = None) -> List[ProviderCategory]:
        """
        Fetch models.
        - is_reasoning=True: Return only reasoning models.
        - is_reasoning=False: Return only standard models.
        - is_reasoning=None: Return ALL models.
        """
        all_data = await model_service.get_cached_data()
        
        reasoning_keys = {"reasoning", "reasoning_effort", "include_reasoning"}
        
        filtered_categories = []
        for cat in all_data:
            filtered_models = []
            for m in cat["models"]:
                # Determine if this model supports reasoning
                supported = set(m.get("supported_parameters", []))
                is_reasoning_model = bool(reasoning_keys.intersection(supported))
                
                # Filter Logic
                if is_reasoning is not None:
                    if is_reasoning and not is_reasoning_model:
                        continue
                    if not is_reasoning and is_reasoning_model:
                        continue

                pricing = ModelPricing(
                    prompt=m["pricing"]["prompt"],
                    completion=m["pricing"]["completion"],
                    unit=m["pricing"]["unit"]
                )
                
                filtered_models.append(Model(
                    id=m["id"],
                    name=m["name"],
                    context_length=m["context_length"],
                    pricing=pricing,
                    supported_parameters=m["supported_parameters"]
                ))
            
            if filtered_models:
                filtered_categories.append(ProviderCategory(name=cat["name"], models=filtered_models))
        
        return filtered_categories

schema = strawberry.Schema(query=Query)
