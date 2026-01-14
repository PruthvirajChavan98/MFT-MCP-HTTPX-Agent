import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import OpenAIEmbeddings
from langchain_groq import ChatGroq

from src.common.neo4j_mgr import Neo4jManager
# Updated import path to core
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

    async def ingest_faq_batch(self, items: List[dict], groq_key: str = None, openrouter_key: str = None) -> dict: # type: ignore
        driver = Neo4jManager.get_driver()
        success_count = 0
        errors = []

        # 0. Setup Embedding Model
        try:
            embeddings = self._get_embeddings(openrouter_key)
        except ValueError as e:
            return {"status": "failed", "error": str(e)}

        # 1. Ensure Constraints
        with driver.session() as session:
            session.run("CREATE CONSTRAINT question_uniq IF NOT EXISTS FOR (q:Question) REQUIRE q.text IS UNIQUE")
            session.run("CREATE CONSTRAINT topic_uniq IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE")
            session.run("CREATE CONSTRAINT product_uniq IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE")
            session.run("""
                CREATE VECTOR INDEX question_embeddings IF NOT EXISTS
                FOR (q:Question) ON (q.embedding)
                OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
            """)

        # 2. Process Items
        for item in items:
            q_text = item.get("question")
            a_text = item.get("answer")
            if not q_text or not a_text: continue

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

        return {"processed": len(items), "success": success_count, "errors": errors}

kb_service = KnowledgeBaseService()