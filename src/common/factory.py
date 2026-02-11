from typing import Optional, Any, Union
from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings

def get_byok_llm(
    model: str, 
    api_key: str, 
    provider: Optional[str] = None, 
    **kwargs
) -> BaseChatModel:
    """
    Production-grade LLM factory.
    Enforces BYOK: Raises ValueError if api_key is missing.
    """
    if not api_key:
        raise ValueError(f"BYOK Error: API Key required for model {model}")

    # init_chat_model automatically handles routing (openai, groq, anthropic, etc.)
    return init_chat_model(
        model=model,
        model_provider=provider,
        api_key=api_key,
        temperature=kwargs.get("temperature", 0.0),
        **kwargs
    )

def get_byok_embeddings(
    model: str, 
    api_key: str, 
    provider: Optional[str] = "openai",
    **kwargs
) -> Embeddings:
    """
    Unified Embedding factory.
    Used for Router classification and Neo4j Vector Search.
    """
    if not api_key:
        raise ValueError(f"BYOK Error: API Key required for embeddings model {model}")

    return init_embeddings(
        model=model,
        provider=provider,
        api_key=api_key,
        **kwargs
    )
