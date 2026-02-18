import argparse
import asyncio
import json
import logging
import os
from typing import List

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agent_service.llm.client import get_embeddings, get_llm

# Enterprise imports (Run from root: python -m scripts.ingest_faq)
from src.common.neo4j_mgr import Neo4jManager

# Setup standard logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ingest_faq")


# --- Metadata Schema ---
class FAQMetadata(BaseModel):
    topics: List[str] = Field(description="General processes e.g., 'Foreclosure', 'CIBIL', 'EMI'")
    products: List[str] = Field(
        description="Financial products e.g., 'HIPL', 'UBL', 'Two-Wheeler', 'Loan Against Property'"
    )
    entities: List[str] = Field(
        description="Contact points e.g., emails like 'customer.care@...', phone numbers, URLs"
    )


async def extract_metadata(text: str, api_key: str, model_name: str) -> FAQMetadata:
    """
    Uses LLM to extract structured tags (Topics, Products, Entities).
    """
    if not api_key:
        log.warning("⚠️ No API Key provided for metadata extraction. Returning empty tags.")
        return FAQMetadata(topics=[], products=[], entities=[])

    try:
        # Dynamic model selection via Enterprise Factory
        llm = get_llm(model_name=model_name, openrouter_api_key=api_key, temperature=0.0)

        parser = PydanticOutputParser(pydantic_object=FAQMetadata)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a Data Engineer. Extract topics, products, and contact entities from the text.\n{format_instructions}",
                ),
                ("human", "{text}"),
            ]
        )

        chain = prompt | llm | parser

        return await chain.ainvoke(
            {"text": text, "format_instructions": parser.get_format_instructions()}
        )
    except Exception as e:
        log.error(f"Metadata extraction failed: {e}")
        return FAQMetadata(topics=[], products=[], entities=[])


async def ingest_data_async(api_key: str, extraction_model: str):
    json_path = os.path.join("data", "mft_faq_data.json")
    if not os.path.exists(json_path):
        log.error(f"❌ File not found: {json_path}")
        return

    with open(json_path, "r") as f:
        data = json.load(f)

    # Initialize Embeddings via Factory
    # Note: Embeddings are usually fixed to the retrieval model (e.g. openai/text-embedding-3-small)
    # to avoid re-indexing the whole DB if the chat model changes.
    try:
        embeddings = get_embeddings(api_key=api_key)
    except Exception as e:
        log.error(f"❌ Embeddings setup failed: {e}")
        return

    driver = Neo4jManager.get_driver()

    # 1. Apply Constraints (Idempotent)
    log.info("🔧 Applying Schema Constraints...")
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

        # Ensure Vector Index Exists (1536 dim for OpenAI small)
        session.run("""
            CREATE VECTOR INDEX question_embeddings IF NOT EXISTS
            FOR (q:Question)
            ON (q.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}
        """)

    log.info(f"🚀 Starting Ingestion of {len(data)} items using model: {extraction_model}...")
    success_count = 0

    for i, item in enumerate(data):
        q_text = item.get("question")
        a_text = item.get("answer")
        if not q_text or not a_text:
            continue

        log.info(f"Processing [{i+1}/{len(data)}]: {q_text[:40]}...")

        # 2. Generate Vector
        try:
            vector = await embeddings.aembed_query(q_text)
        except Exception as e:
            log.error(f"  ⚠️ Embedding failed: {e}")
            continue

        # 3. Base Ingestion (Merge Question & Answer)
        query_base = """
        MERGE (q:Question {text: $q})
        ON CREATE SET q.embedding = $vector
        ON MATCH SET q.embedding = $vector
        MERGE (a:Answer {text: $a})
        MERGE (q)-[:HAS_ANSWER]->(a)
        """

        try:
            Neo4jManager.execute_write(query_base, {"q": q_text, "a": a_text, "vector": vector})
        except Exception as e:
            log.error(f"  ⚠️ DB Write failed: {e}")
            continue

        # 4. AI Enrichment (Metadata extraction)
        meta = await extract_metadata(
            text=f"Question: {q_text}\nAnswer: {a_text}",
            api_key=api_key,
            model_name=extraction_model,
        )

        if meta.topics or meta.products:
            with driver.session() as session:
                # Link Topics
                for t in meta.topics:
                    session.run(
                        """
                        MATCH (q:Question {text: $q})
                        MERGE (top:Topic {name: $t})
                        MERGE (q)-[:ABOUT]->(top)
                    """,
                        q=q_text,
                        t=t,
                    )

                # Link Products
                for p in meta.products:
                    session.run(
                        """
                        MATCH (q:Question {text: $q})
                        MERGE (prod:Product {name: $p})
                        MERGE (q)-[:RELATES_TO]->(prod)
                    """,
                        q=q_text,
                        p=p,
                    )

            log.info(f"  -> Enriched: {len(meta.topics)} topics, {len(meta.products)} products")

        success_count += 1

    log.info(f"\n✅ Ingestion Complete. Processed {success_count}/{len(data)} items.")
    Neo4jManager.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest FAQ data into Neo4j with AI enrichment.")

    # Required: API Key
    parser.add_argument("--api-key", type=str, required=True, help="OpenRouter/Provider API Key")

    # Optional: Model Selection (Frontend controlled)
    parser.add_argument(
        "--model",
        type=str,
        default="openai/gpt-4o-mini",
        help="Model ID to use for metadata extraction (default: openai/gpt-4o-mini)",
    )

    args = parser.parse_args()

    # Run Async Logic
    asyncio.run(ingest_data_async(args.api_key, args.model))
