# ===== graph_tool.py =====
from __future__ import annotations

import os
from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from langchain_neo4j import Neo4jVector
from langchain_openai import OpenAIEmbeddings

from src.common.neo4j_mgr import Neo4jManager
from src.agent_service.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL

class GraphQueryInput(BaseModel):
    """Input for the Hero Fincorp Graph Tool."""
    query: str = Field(
        description="A natural language question. Example: 'How do I close my loan?' or 'Contact for stolen bike'."
    )

class _GraphVectorSingleton:
    _vector_store: Optional[Neo4jVector] = None
    _embeddings: Optional[OpenAIEmbeddings] = None

    @classmethod
    def get_vector_store(cls) -> Neo4jVector:
        if cls._vector_store is not None:
            return cls._vector_store

        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is not set (required for embeddings).")

        # 1) Embeddings (via OpenRouter OpenAI-compatible base)
        cls._embeddings = OpenAIEmbeddings(
            model="openai/text-embedding-3-small",
            api_key=OPENROUTER_API_KEY,  # type: ignore
            base_url=OPENROUTER_BASE_URL,
            check_embedding_ctx_length=False,
        )

        # 2) Neo4j Vector index (existing)
        cls._vector_store = Neo4jVector.from_existing_graph(
            embedding=cls._embeddings,
            url=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
            index_name="question_embeddings",
            node_label="Question",
            text_node_properties=["text"],
            embedding_node_property="embedding",
        )
        return cls._vector_store

def query_hero_fincorp(query: str) -> str:
    """
    Performs a Vector Search on the Hero Fincorp Knowledge Graph (Neo4j).
    """
    try:
        vector_store = _GraphVectorSingleton.get_vector_store()
        results = vector_store.similarity_search(query, k=2)

        if not results:
            return "No relevant information found in the knowledge base."

        response = "Here are the relevant FAQs found:\n\n"
        driver = Neo4jManager.get_driver()

        with driver.session() as session:
            for doc in results:
                raw_content = doc.page_content or ""
                if "text: " in raw_content:
                    q_text = raw_content.split("text: ", 1)[1].strip()
                else:
                    q_text = raw_content.strip()

                record = session.run(
                    """
                    MATCH (q:Question {text: $q_text})-[:HAS_ANSWER]->(a:Answer)
                    RETURN a.text as answer
                    """,
                    q_text=q_text,
                ).single()

                answer = record["answer"] if record else "No answer linked."
                response += f"**Q:** {q_text}\n**A:** {answer}\n\n"

        return response

    except Exception as e:
        return f"Knowledge Base Error: {str(e)}"

def create_graph_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=query_hero_fincorp,
        name="hero_fincorp_knowledge_base",
        description="Search the Hero Fincorp FAQs database using vector semantic search. Use this for questions about processes, documents, contacts, loan products and miscellaneous questions.",
        args_schema=GraphQueryInput,
    )