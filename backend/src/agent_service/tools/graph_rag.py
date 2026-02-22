from __future__ import annotations

import os

from langchain_core.tools import StructuredTool
from langchain_neo4j import Neo4jVector
from pydantic import BaseModel, Field

from src.agent_service.llm.client import get_embeddings
from src.common.neo4j_mgr import neo4j_mgr


class GraphQueryInput(BaseModel):
    query: str = Field(description="Natural language question to search.")


def create_graph_tool(openrouter_api_key: str) -> StructuredTool:
    async def query_faq(query: str) -> str:
        try:
            embeddings = get_embeddings(api_key=openrouter_api_key)

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

            results = vector_store.similarity_search_with_score(query, k=2)
            if not results:
                return "No relevant information found."

            response = "Relevant FAQs:\n\n"
            async with neo4j_mgr._driver.session() as session:
                for doc, score in results:
                    q_text = doc.page_content.replace("text: ", "").strip()

                    result = await session.run(
                        "MATCH (q:Question {text: $q})-[:HAS_ANSWER]->(a:Answer) RETURN a.text as a",
                        {"q": q_text},
                    )
                    record = await result.single()

                    ans = record["a"] if record else "No answer."
                    response += f"Q: {q_text}\nA: {ans}\n(Score: {score:.2f})\n\n"

            return response

        except Exception as e:
            return f"Error querying knowledge base: {str(e)}"

    return StructuredTool.from_function(
        func=query_faq,
        name="mock_fintech_knowledge_base",
        description="Search FAQs database.",
        args_schema=GraphQueryInput,
    )
