import logging
from typing import List, Optional
import json
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import OpenAIEmbeddings
from langchain_groq import ChatGroq


from src.common.neo4j_mgr import Neo4jManager
from src.agent_service.core.config import (
    GROQ_KEY_CYCLE, 
    GROQ_BASE_URL,
    OPENROUTER_API_KEY, 
    OPENROUTER_BASE_URL
)

log = logging.getLogger("knowledge_base")

# --- Metadata Schema ---
class FAQMetadata(BaseModel):
    topics: List[str] = Field(description="General processes e.g., 'Foreclosure', 'CIBIL', 'EMI'")
    products: List[str] = Field(description="Financial products e.g., 'HIPL', 'UBL', 'Two-Wheeler', 'Loan Against Property'")
    entities: List[str] = Field(description="Contact points e.g., emails like 'customer.care@...', phone numbers, URLs")

class KnowledgeBaseService:
    def __init__(self):
        # Default Embeddings (System Config)
        if OPENROUTER_API_KEY:
            self.default_embeddings = OpenAIEmbeddings(
                model="openai/text-embedding-3-small",
                api_key=OPENROUTER_API_KEY, # type: ignore
                base_url=OPENROUTER_BASE_URL,
                check_embedding_ctx_length=False
            )
        else:
            self.default_embeddings = None

    def _get_embeddings(self, custom_key: str = None): # type: ignore
        """Use custom key if provided, else fall back to system default."""
        if custom_key:
            return OpenAIEmbeddings(
                model="openai/text-embedding-3-small",
                api_key=custom_key, # type: ignore
                base_url=OPENROUTER_BASE_URL,
                check_embedding_ctx_length=False
            )
        if not self.default_embeddings:
            raise ValueError("No OpenRouter Key configured (System or Request).")
        return self.default_embeddings

    def _get_metadata_chain(self, custom_key: str = None): # type: ignore
        """
        1. If custom_key provided: Use it (Bypass Cycle).
        2. If no custom_key: Use next(GROQ_KEY_CYCLE) (Internal Load Balancing).
        """
        api_key = None
        
        if custom_key:
            api_key = custom_key
        elif GROQ_KEY_CYCLE:
            api_key = next(GROQ_KEY_CYCLE) # Round Robin
        else:
            raise ValueError("No Groq Keys available (System or Request).")
        
        llm = ChatGroq(
            api_key=api_key, # type: ignore
            model="openai/gpt-oss-120b",
            temperature=0.0,
            base_url=GROQ_BASE_URL
        )
        
        parser = PydanticOutputParser(pydantic_object=FAQMetadata)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a Data Engineer. Extract topics, products, and contact entities from the text.\n{format_instructions}"),
            ("human", "{text}")
        ])
        
        return prompt | llm | parser

    async def ingest_faq_batch_gen(self, items: List[dict], groq_key: str = None, openrouter_key: str = None):
        """
        Generator that yields progress updates while ingesting FAQs.
        """
        driver = Neo4jManager.get_driver()
        total_items = len(items)
        success_count = 0
        errors = []

        yield {"event": "progress", "data": json.dumps({"percent": 5, "message": "Initializing Embeddings & Constraints..."})}

        # 0. Setup Embedding Model
        try:
            embeddings = self._get_embeddings(openrouter_key)
        except ValueError as e:
            yield {"event": "error", "data": str(e)}
            return

        # 1. Ensure Constraints (Fast)
        try:
            with driver.session() as session:
                session.run("CREATE CONSTRAINT question_uniq IF NOT EXISTS FOR (q:Question) REQUIRE q.text IS UNIQUE")
                session.run("CREATE CONSTRAINT topic_uniq IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE")
                session.run("CREATE CONSTRAINT product_uniq IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE")
                session.run("""
                    CREATE VECTOR INDEX question_embeddings IF NOT EXISTS
                    FOR (q:Question) ON (q.embedding)
                    OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
                """)
        except Exception as e:
            log.error(f"Constraint Error: {e}")
            # Continue anyway, constraints might already exist

        # 2. Process Items Loop
        for i, item in enumerate(items):
            q_text = item.get("question")
            a_text = item.get("answer")
            
            # Calculate granular progress (Start at 10%, end at 95%)
            percent = 10 + int((i / total_items) * 85)
            yield {"event": "progress", "data": json.dumps({
                "percent": percent, 
                "message": f"Processing {i+1}/{total_items}: {q_text[:30]}..."
            })}

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

                # C. Extract Metadata (Load Balanced or Custom Key)
                chain = self._get_metadata_chain(custom_key=groq_key)
                
                meta = await chain.ainvoke({
                    "text": f"Question: {q_text}\nAnswer: {a_text}",
                    "format_instructions": chain.last.get_format_instructions() # type: ignore
                })

                # D. Link Metadata
                with driver.session() as session:
                    for t in meta.topics:
                        session.run("MATCH (q:Question {text: $q}) MERGE (top:Topic {name: $t}) MERGE (q)-[:ABOUT]->(top)", q=q_text, t=t)
                    for p in meta.products:
                        session.run("MATCH (q:Question {text: $q}) MERGE (prod:Product {name: $p}) MERGE (q)-[:RELATES_TO]->(prod)", q=q_text, p=p)

                success_count += 1
            
            except Exception as e:
                log.error(f"Failed to ingest FAQ '{q_text[:20]}...': {e}")
                errors.append({"question": q_text, "error": str(e)})

        # Final Result
        yield {
            "event": "done", 
            "data": json.dumps({
                "processed": total_items, 
                "success": success_count, 
                "errors": errors
            })
        }

    # --- NEW METHOD ADDED HERE ---
    async def get_all_faqs(self, limit: int = 100, skip: int = 0) -> List[dict]:
        """
        Retrieves existing FAQs from Neo4j.
        """
        query = """
        MATCH (q:Question)-[:HAS_ANSWER]->(a:Answer)
        RETURN q.text as question, a.text as answer
        ORDER BY q.text
        SKIP $skip LIMIT $limit
        """
        try:
            # Using execute_read from Neo4jManager
            results = Neo4jManager.execute_read(query, {"skip": skip, "limit": limit})
            return [{"question": r["question"], "answer": r["answer"]} for r in results]
        except Exception as e:
            log.error(f"Failed to fetch FAQs: {e}")
            raise e

    async def edit_faq(self, original_question: str, new_question: str = None, new_answer: str = None, openrouter_key: str = None) -> dict:
        """
        Updates an FAQ. If the question text changes, it regenerates the embedding.
        """
        driver = Neo4jManager.get_driver()
        
        # 1. Verify existence
        verify_query = "MATCH (q:Question {text: $q}) RETURN q"
        exists = Neo4jManager.execute_read(verify_query, {"q": original_question})
        if not exists:
            return {"status": "error", "message": "FAQ not found. Check exact spelling of the original question."}

        updates = []
        params = {"orig_q": original_question}

        # 2. Handle Answer Update
        if new_answer:
            updates.append("SET a.text = $new_a")
            params["new_a"] = new_answer

        # 3. Handle Question Update (Expensive: requires embedding gen)
        if new_question and new_question != original_question:
            try:
                embeddings = self._get_embeddings(openrouter_key)
                # Generate new vector for the new question text
                new_vector = await embeddings.aembed_query(new_question)
                
                updates.append("SET q.text = $new_q, q.embedding = $new_vec")
                params["new_q"] = new_question
                params["new_vec"] = new_vector
            except Exception as e:
                return {"status": "error", "message": f"Failed to generate embedding: {str(e)}"}

        if not updates:
            return {"status": "ignored", "message": "No changes provided"}

        # 4. Execute Cypher Update
        # Updates both q and a nodes found via the relationship
        cypher = f"""
        MATCH (q:Question {{text: $orig_q}})-[:HAS_ANSWER]->(a:Answer)
        { " ".join(updates) }
        RETURN q.text as q, a.text as a
        """
        
        try:
            Neo4jManager.execute_write(cypher, params)
            return {
                "status": "success", 
                "original_question": original_question, 
                "updated_fields": list(params.keys())
            }
        except Exception as e:
            log.error(f"Error updating FAQ: {e}")
            return {"status": "error", "message": str(e)}

    async def delete_faq(self, question: str) -> dict:
        """
        Deletes a specific FAQ by its question text. 
        Uses DETACH DELETE to remove relationships (to Answers/Topics) before deleting the node.
        """
        # Cypher to find the question node and delete it
        query = "MATCH (q:Question {text: $q}) DETACH DELETE q"
        
        try:
            # Execute write transaction
            Neo4jManager.execute_write(query, {"q": question})
            return {"status": "success", "message": "FAQ deleted", "question": question}
        except Exception as e:
            log.error(f"Error deleting FAQ: {e}")
            return {"status": "error", "message": str(e)}

    async def clear_all_faqs(self) -> dict:
        """
        Wipes all Question, Answer, Topic, and Product nodes from the database.
        Use with caution.
        """
        # Cypher to detach delete everything related to the FAQ schema
        query = """
        MATCH (q:Question) DETACH DELETE q;
        """
        # Note: You might want to also cleanup orphan Answers/Topics if they aren't connected to anything else
        # For now, deleting Questions and their relationships is the primary goal.
        
        # A more aggressive cleanup (optional, careful if these nodes are shared):
        # MATCH (n) WHERE n:Question OR n:Answer OR n:Topic OR n:Product DETACH DELETE n
        
        try:
            # We'll just delete Questions and Answers for now to be safe, 
            # or use the specific label targeting your FAQ schema.
            Neo4jManager.execute_write("MATCH (q:Question) DETACH DELETE q")
            Neo4jManager.execute_write("MATCH (a:Answer) WHERE NOT (a)<-[:HAS_ANSWER]-(:Question) DETACH DELETE a")
            
            return {"status": "success", "message": "Knowledge base cleared."}
        except Exception as e:
            log.error(f"Error clearing KB: {e}")
            return {"status": "error", "message": str(e)}

    async def semantic_search(self, query: str, limit: int = 5, openrouter_key: str = None) -> List[dict]:
        """
        Finds FAQs semantically similar to the query.
        """
        try:
            embeddings = self._get_embeddings(openrouter_key)
            vector = await embeddings.aembed_query(query)
            
            # Neo4j Vector Search Query
            cypher = """
            CALL db.index.vector.queryNodes('question_embeddings', $limit, $vector)
            YIELD node, score
            MATCH (node)-[:HAS_ANSWER]->(a:Answer)
            RETURN node.text as question, a.text as answer, score
            """
            
            results = Neo4jManager.execute_read(cypher, {"vector": vector, "limit": limit})
            return results
        except Exception as e:
            log.error(f"Semantic Search Error: {e}")
            raise e

    async def delete_faq_by_vector(self, query: str, threshold: float = 0.92, openrouter_key: str = None) -> dict:
        """
        Finds the most similar FAQ and deletes it if the score > threshold.
        """
        try:
            embeddings = self._get_embeddings(openrouter_key)
            vector = await embeddings.aembed_query(query)
            
            # Find best match
            find_query = """
            CALL db.index.vector.queryNodes('question_embeddings', 1, $vector)
            YIELD node, score
            WHERE score > $threshold
            MATCH (node)-[:HAS_ANSWER]->(a:Answer)
            RETURN node.text as question, score
            """
            
            match = Neo4jManager.execute_read(find_query, {"vector": vector, "threshold": threshold})
            
            if not match:
                return {"status": "ignored", "message": "No matching FAQ found with high confidence."}
            
            target_question = match[0]['question']
            
            # Delegate to existing delete logic
            return await self.delete_faq(target_question)
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

kb_service = KnowledgeBaseService()