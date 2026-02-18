import json
import logging
from typing import List, Optional

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agent_service.llm.client import get_embeddings, get_llm

# Enterprise Imports
from src.common.neo4j_mgr import Neo4jManager

log = logging.getLogger("knowledge_base")


# --- Metadata Schema ---
class FAQMetadata(BaseModel):
    topics: List[str] = Field(description="General processes e.g., 'Foreclosure', 'CIBIL', 'EMI'")
    products: List[str] = Field(description="Financial products e.g., 'HIPL', 'UBL', 'Two-Wheeler'")
    entities: List[str] = Field(description="Contact points e.g., emails, phone numbers, URLs")


class KnowledgeBaseService:
    def __init__(self):
        pass

    async def _get_metadata_chain(self, custom_key: Optional[str] = None):
        """
        Uses the Enterprise LLM Factory for extraction.
        Defaults to a cheap/fast model if available.
        """
        # In a BYOK architecture, we expect custom_key to be provided.
        # If missing, get_llm will raise a clear ValueError.

        llm = get_llm(
            model_name="openai/gpt-4o-mini",  # Use efficient model for extraction
            openrouter_api_key=custom_key,
            temperature=0.0,
        )

        parser = PydanticOutputParser(pydantic_object=FAQMetadata)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a Data Engineer. Extract topics, products, and contact entities.\n{format_instructions}",
                ),
                ("human", "{text}"),
            ]
        )

        return prompt | llm | parser

    async def ingest_faq_batch_gen(
        self, items: List[dict], groq_key: str = None, openrouter_key: str = None
    ):
        """
        Generator that yields progress updates while ingesting FAQs.
        """
        # Prioritize OpenRouter key if available, else Groq (for extraction only)
        extract_key = openrouter_key or groq_key

        if not openrouter_key:
            yield {"event": "error", "data": "OpenRouter API Key required for Embeddings"}
            return

        driver = Neo4jManager.get_driver()
        total_items = len(items)
        success_count = 0
        errors = []

        yield {
            "event": "progress",
            "data": json.dumps({"percent": 5, "message": "Initializing..."}),
        }

        try:
            embeddings = get_embeddings(api_key=openrouter_key)
        except ValueError as e:
            yield {"event": "error", "data": str(e)}
            return

        # 1. Ensure Constraints
        try:
            with driver.session() as session:
                session.run(
                    "CREATE CONSTRAINT question_uniq IF NOT EXISTS FOR (q:Question) REQUIRE q.text IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT topic_uniq IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT product_uniq IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE"
                )
                session.run("""
                    CREATE VECTOR INDEX question_embeddings IF NOT EXISTS
                    FOR (q:Question) ON (q.embedding)
                    OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
                """)
        except Exception as e:
            log.warning(f"Constraint check failed (non-fatal): {e}")

        # 2. Process Items
        try:
            chain = await self._get_metadata_chain(custom_key=extract_key)
            format_instructions = chain.last.get_format_instructions()
        except Exception as e:
            yield {"event": "error", "data": f"Failed to init metadata chain: {e}"}
            return

        for i, item in enumerate(items):
            q_text = item.get("question")
            a_text = item.get("answer")

            percent = 10 + int((i / total_items) * 85)
            yield {
                "event": "progress",
                "data": json.dumps(
                    {
                        "percent": percent,
                        "message": f"Processing {i+1}/{total_items}: {q_text[:30]}...",
                    }
                ),
            }

            if not q_text or not a_text:
                continue

            try:
                # A. Generate Vector
                vector = await embeddings.aembed_query(q_text)

                # B. Write Base Node
                query_base = """
                MERGE (q:Question {text: $q})
                ON CREATE SET q.embedding = $vector
                ON MATCH SET q.embedding = $vector
                MERGE (a:Answer {text: $a})
                MERGE (q)-[:HAS_ANSWER]->(a)
                """
                Neo4jManager.execute_write(query_base, {"q": q_text, "a": a_text, "vector": vector})

                # C. Extract & Link Metadata
                try:
                    meta = await chain.ainvoke(
                        {
                            "text": f"Question: {q_text}\nAnswer: {a_text}",
                            "format_instructions": format_instructions,
                        }
                    )

                    with driver.session() as session:
                        for t in meta.topics:
                            session.run(
                                "MATCH (q:Question {text: $q}) MERGE (top:Topic {name: $t}) MERGE (q)-[:ABOUT]->(top)",
                                q=q_text,
                                t=t,
                            )
                        for p in meta.products:
                            session.run(
                                "MATCH (q:Question {text: $q}) MERGE (prod:Product {name: $p}) MERGE (q)-[:RELATES_TO]->(prod)",
                                q=q_text,
                                p=p,
                            )
                except Exception as e:
                    log.warning(f"Metadata extraction failed for '{q_text[:10]}': {e}")

                success_count += 1

            except Exception as e:
                log.error(f"Ingest error: {e}")
                errors.append({"question": q_text, "error": str(e)})

        yield {
            "event": "done",
            "data": json.dumps(
                {"processed": total_items, "success": success_count, "errors": errors}
            ),
        }

    async def get_all_faqs(self, limit: int = 100, skip: int = 0) -> List[dict]:
        query = """
        MATCH (q:Question)-[:HAS_ANSWER]->(a:Answer)
        RETURN q.text as question, a.text as answer
        ORDER BY q.text
        SKIP $skip LIMIT $limit
        """
        try:
            results = Neo4jManager.execute_read(query, {"skip": skip, "limit": limit})
            return [{"question": r["question"], "answer": r["answer"]} for r in results]
        except Exception as e:
            log.error(f"Failed to fetch FAQs: {e}")
            raise e

    async def edit_faq(
        self,
        original_question: str,
        new_question: str = None,
        new_answer: str = None,
        openrouter_key: str = None,
    ) -> dict:
        if not original_question:
            return {"status": "error", "message": "Original question required"}

        updates = []
        params = {"orig_q": original_question}

        if new_answer:
            updates.append("SET a.text = $new_a")
            params["new_a"] = new_answer

        if new_question and new_question != original_question:
            if not openrouter_key:
                return {
                    "status": "error",
                    "message": "OpenRouter Key required to update question text (re-embedding needed).",
                }
            try:
                embeddings = get_embeddings(api_key=openrouter_key)
                new_vector = await embeddings.aembed_query(new_question)
                updates.append("SET q.text = $new_q, q.embedding = $new_vec")
                params["new_q"] = new_question
                params["new_vec"] = new_vector
            except Exception as e:
                return {"status": "error", "message": f"Embedding failed: {e}"}

        if not updates:
            return {"status": "ignored", "message": "No changes"}

        cypher = f"""
        MATCH (q:Question {{text: $orig_q}})-[:HAS_ANSWER]->(a:Answer)
        { " ".join(updates) }
        RETURN q.text as q
        """

        try:
            Neo4jManager.execute_write(cypher, params)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def delete_faq(self, question: str) -> dict:
        try:
            Neo4jManager.execute_write(
                "MATCH (q:Question {text: $q}) DETACH DELETE q", {"q": question}
            )
            return {"status": "success", "question": question}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def clear_all_faqs(self) -> dict:
        try:
            Neo4jManager.execute_write("MATCH (q:Question) DETACH DELETE q")
            Neo4jManager.execute_write(
                "MATCH (a:Answer) WHERE NOT (a)<-[:HAS_ANSWER]-(:Question) DETACH DELETE a"
            )
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def semantic_search(
        self, query: str, limit: int = 5, openrouter_key: str = None
    ) -> List[dict]:
        if not openrouter_key:
            raise ValueError("OpenRouter Key required for semantic search")
        try:
            embeddings = get_embeddings(api_key=openrouter_key)
            vector = await embeddings.aembed_query(query)

            cypher = """
            CALL db.index.vector.queryNodes('question_embeddings', $limit, $vector)
            YIELD node, score
            MATCH (node)-[:HAS_ANSWER]->(a:Answer)
            RETURN node.text as question, a.text as answer, score
            """
            return Neo4jManager.execute_read(cypher, {"vector": vector, "limit": limit})
        except Exception as e:
            log.error(f"Search failed: {e}")
            raise e

    async def get_metadata_tags(self) -> dict:
        """Dynamic filters for Frontend."""
        query = """
        MATCH (t:Topic) WITH collect(DISTINCT t.name) as topics
        MATCH (p:Product) WITH topics, collect(DISTINCT p.name) as products
        RETURN topics, products
        """
        try:
            result = Neo4jManager.execute_read(query)
            if not result:
                return {"topics": [], "products": []}
            row = result[0]
            return {
                "topics": sorted(row.get("topics", [])),
                "products": sorted(row.get("products", [])),
                "entities": [],
            }
        except Exception:
            return {"topics": [], "products": [], "entities": []}

    async def delete_faq_by_vector(
        self, query: str, threshold: float = 0.92, openrouter_key: str = None
    ) -> dict:
        if not openrouter_key:
            return {"status": "error", "message": "Key required"}
        try:
            embeddings = get_embeddings(api_key=openrouter_key)
            vector = await embeddings.aembed_query(query)

            find_query = """
            CALL db.index.vector.queryNodes('question_embeddings', 1, $vector)
            YIELD node, score WHERE score > $threshold
            RETURN node.text as question
            """
            match = Neo4jManager.execute_read(
                find_query, {"vector": vector, "threshold": threshold}
            )
            if not match:
                return {"status": "ignored", "message": "No match found"}

            return await self.delete_faq(match[0]["question"])
        except Exception as e:
            return {"status": "error", "message": str(e)}


kb_service = KnowledgeBaseService()
