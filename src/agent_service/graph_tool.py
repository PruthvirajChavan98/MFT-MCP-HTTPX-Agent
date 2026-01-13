import os
from typing import Optional, List
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from langchain_neo4j import Neo4jVector
from langchain_openai import OpenAIEmbeddings

from src.common.neo4j_mgr import Neo4jManager

class GraphQueryInput(BaseModel):
    """Input for the Hero Fincorp Graph Tool."""
    query: str = Field(
        description="A natural language question. Example: 'How do I close my loan?' or 'Contact for stolen bike'."
    )

def query_hero_fincorp(query: str) -> str:
    """
    Performs a Vector Search on the Hero Fincorp Knowledge Graph (Neo4j).
    """
    try:
        # 1. Initialize Embeddings
        embeddings = OpenAIEmbeddings(
            model="openai/text-embedding-3-small",
            api_key="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", # type: ignore
            base_url="https://openrouter.ai/api/v1",
            check_embedding_ctx_length=False
        )

        # 2. Connect to Neo4j Vector Index
        vector_store = Neo4jVector.from_existing_graph(
            embedding=embeddings,
            url=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
            index_name="question_embeddings",
            node_label="Question",
            text_node_properties=["text"],
            embedding_node_property="embedding",
        )

        # 3. Perform Similarity Search
        results = vector_store.similarity_search(query, k=2)
        
        if not results:
            return "No relevant information found in the knowledge base."

        response = "Here are the relevant FAQs found:\n\n"
        driver = Neo4jManager.get_driver()
        
        with driver.session() as session:
            for doc in results:
                # FIX: Clean the content. LangChain adds "text: " prefix which breaks the exact match.
                raw_content = doc.page_content
                if "text: " in raw_content:
                    q_text = raw_content.split("text: ")[1].strip()
                else:
                    q_text = raw_content.strip()

                # Retrieve the answer connected to this specific question
                record = session.run("""
                    MATCH (q:Question {text: $q_text})-[:HAS_ANSWER]->(a:Answer)
                    RETURN a.text as answer
                """, q_text=q_text).single()
                
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
        args_schema=GraphQueryInput
    )