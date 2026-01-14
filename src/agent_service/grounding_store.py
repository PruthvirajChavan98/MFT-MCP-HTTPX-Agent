# src/agent_service/grounding_store.py
import os
from typing import Optional
from langchain_neo4j import Neo4jVector
from langchain_openai import OpenAIEmbeddings
from src.agent_service.config import OPENROUTER_BASE_URL

class _GroundingVectorSingleton:
    """
    Dedicated Vector Store for Follow-Up Question Grounding.
    Uses a separate index ('grounding_embeddings') to avoid interference with main FAQ search.
    """
    _instance: Optional[Neo4jVector] = None

    @classmethod
    def get_vector_store(cls, api_key: Optional[str] = None) -> Neo4jVector:
        if api_key:
            return cls._create_store(api_key)
        
        # We don't cache the instance if it depends on a dynamic user key (BYOK),
        # but if you have a system key, you could cache it here.
        # For safety in BYOK, we recreate light-weight wrappers.
        if not api_key:
             raise ValueError("API Key required for Grounding Store.")
             
        return cls._create_store(api_key)

    @staticmethod
    def _create_store(key: str) -> Neo4jVector:
        embeddings = OpenAIEmbeddings(
            model="openai/text-embedding-3-small",
            api_key=key, # type: ignore
            base_url=OPENROUTER_BASE_URL,
            check_embedding_ctx_length=False,
        )

        return Neo4jVector.from_existing_graph(
            embedding=embeddings,
            url=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
            # --- DIFFERENT INDEX ---
            index_name="grounding_embeddings", 
            node_label="GroundingQuestion", # Different Node Label
            text_node_properties=["text"],
            embedding_node_property="embedding",
        )