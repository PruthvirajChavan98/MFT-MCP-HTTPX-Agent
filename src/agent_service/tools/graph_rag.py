from __future__ import annotations
import os
from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from langchain_neo4j import Neo4jVector
from langchain_openai import OpenAIEmbeddings

from src.common.neo4j_mgr import Neo4jManager
# Updated import path to core
from src.agent_service.core.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL

class GraphQueryInput(BaseModel):
    """Input for the Hero Fincorp Graph Tool."""
    query: str = Field(
        description="A natural language question. Example: 'How do I close my loan?' or 'Contact for stolen bike'."
    )

class _GraphVectorSingleton:
    _instance: Optional[Neo4jVector] = None

    @classmethod
    def get_vector_store(cls, api_key: Optional[str] = None) -> Neo4jVector:
        # If a specific user key is provided, create a fresh instance (BYOK)
        # We do NOT cache this in the singleton to avoid leaking keys between requests/users
        if api_key:
            return cls._create_store(api_key)

        # If no key, fall back to the system singleton (Env Var)
        if cls._instance is not None:
            return cls._instance

        # Initialize system singleton
        sys_key = OPENROUTER_API_KEY
        if not sys_key:
            raise ValueError("OPENROUTER_API_KEY is not set (required for embeddings).")
        
        cls._instance = cls._create_store(sys_key)
        return cls._instance

    @staticmethod
    def _create_store(key: str) -> Neo4jVector:
        if not key:
             raise ValueError("API Key for embeddings is missing.")

        embeddings = OpenAIEmbeddings(
            model="openai/text-embedding-3-small",
            api_key=key,  # type: ignore
            base_url=OPENROUTER_BASE_URL,
            check_embedding_ctx_length=False,
        )

        return Neo4jVector.from_existing_graph(
            embedding=embeddings,
            url=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
            index_name="question_embeddings",
            node_label="Question",
            text_node_properties=["text"],
            embedding_node_property="embedding",
        )

def create_graph_tool(openrouter_api_key: Optional[str] = None) -> StructuredTool:
    """
    Creates the FAQ search tool.
    Allows injecting a dynamic OpenRouter API Key for embeddings.
    """
    
    # We define the function inside so it captures 'openrouter_api_key' from this scope
    def query_hero_fincorp_wrapper(query: str) -> str:
        """
        Performs a Vector Search on the Hero Fincorp Knowledge Graph (Neo4j).
        """
        try:
            # Pass the dynamic key (or None) to the factory
            vector_store = _GraphVectorSingleton.get_vector_store(api_key=openrouter_api_key)
            
            # This returns List[Tuple[Document, float]]
            results_with_scores = vector_store.similarity_search_with_score(query, k=2)

            if not results_with_scores:
                return "No relevant information found in the knowledge base."

            response = "Here are the relevant FAQs found:\n\n"
            driver = Neo4jManager.get_driver()

            with driver.session() as session:
                for doc, score in results_with_scores:
                    raw_content = doc.page_content or ""
                    
                    # Check if 'text: ' prefix exists from previous ingestions
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
                    
                    response += f"**Q:** {q_text}\n**A:** {answer}\n*(Similarity Score: {score:.4f})*\n\n"

            return response

        except Exception as e:
            return f"Knowledge Base Error: {str(e)}"

    return StructuredTool.from_function(
        func=query_hero_fincorp_wrapper,
        name="hero_fincorp_knowledge_base",
        description="Search the Hero Fincorp FAQs database using vector semantic search. Use this for questions about processes, documents, contacts, loan products and miscellaneous questions.",
        args_schema=GraphQueryInput,
    )