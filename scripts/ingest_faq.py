import json
import os
import sys
import argparse
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import OpenAIEmbeddings

# Fix path to import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.neo4j_mgr import Neo4jManager

# --- Metadata Schema ---
class FAQMetadata(BaseModel):
    topics: List[str] = Field(description="General processes e.g., 'Foreclosure', 'CIBIL', 'EMI'")
    products: List[str] = Field(description="Financial products e.g., 'HIPL', 'UBL', 'Two-Wheeler', 'Loan Against Property'")
    entities: List[str] = Field(description="Contact points e.g., emails like 'customer.care@...', phone numbers, URLs")

def get_embeddings_model(api_key: str):
    """Configures OpenAIEmbeddings to point to OpenRouter."""
    if not api_key:
        raise ValueError("OpenRouter API Key is required for embeddings.")
        
    return OpenAIEmbeddings(
        model="openai/text-embedding-3-small",
        api_key=api_key,  # type: ignore
        base_url="https://openrouter.ai/api/v1",
        check_embedding_ctx_length=False
    )

def extract_metadata(text: str, api_key: str) -> FAQMetadata:
    """
    Uses Groq to extract structured tags. 
    """
    if not api_key:
        # Fallback to an empty metadata object if no key provided, or raise error
        print("⚠️ Warning: No Groq Key provided, skipping metadata extraction.")
        return FAQMetadata(topics=[], products=[], entities=[])

    llm = ChatGroq(
        api_key=api_key,  # type: ignore
        model="openai/gpt-oss-120b",
        temperature=0.0
    )
    
    # 1. Set up the parser
    parser = PydanticOutputParser(pydantic_object=FAQMetadata)
    
    # 2. Inject format instructions into the prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Data Engineer. Extract topics, products, and contact entities from the text.\n{format_instructions}"),
        ("human", "{text}")
    ])
    
    # 3. Create a standard chain (Prompt -> LLM -> Parser)
    chain = prompt | llm | parser
    
    return chain.invoke({
        "text": text,
        "format_instructions": parser.get_format_instructions()
    })

def ingest_data(groq_key: str, openrouter_key: str):
    json_path = os.path.join("data", "hfcl_faq_data.json")
    if not os.path.exists(json_path):
        print(f"❌ File not found: {json_path}")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)

    driver = Neo4jManager.get_driver()
    
    try:
        embeddings = get_embeddings_model(openrouter_key)
    except ValueError as e:
        print(f"❌ Setup Error: {e}")
        return

    # 1. Apply Constraints (Idempotent)
    with driver.session() as session:
        session.run("CREATE CONSTRAINT question_uniq IF NOT EXISTS FOR (q:Question) REQUIRE q.text IS UNIQUE")
        session.run("CREATE CONSTRAINT topic_uniq IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE")
        session.run("CREATE CONSTRAINT product_uniq IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE")
        
        # Ensure Vector Index Exists (1536 dim for OpenAI)
        session.run("""
            CREATE VECTOR INDEX question_embeddings IF NOT EXISTS
            FOR (q:Question)
            ON (q.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}
        """)

    print(f"🚀 Starting Ingestion of {len(data)} items...")
    success_count = 0

    for i, item in enumerate(data):
        q = item.get("question")
        a = item.get("answer")
        if not q or not a: continue

        print(f"Processing [{i+1}/{len(data)}]: {q[:40]}...")

        # 2. Generate Vector (OpenRouter)
        try:
            vector = embeddings.embed_query(q)
        except Exception as e:
            print(f"  ⚠️ Embedding failed: {e}")
            continue

        # 3. Base Ingestion
        query_base = """
        MERGE (q:Question {text: $q})
        ON CREATE SET q.embedding = $vector
        ON MATCH SET q.embedding = $vector
        MERGE (a:Answer {text: $a})
        MERGE (q)-[:HAS_ANSWER]->(a)
        """
        Neo4jManager.execute_write(query_base, {"q": q, "a": a, "vector": vector})

        # 4. AI Enrichment
        try:
            # Combine Q and A for context
            meta = extract_metadata(f"Question: {q}\nAnswer: {a}", api_key=groq_key)
            
            with driver.session() as session:
                # Link Topics
                for t in meta.topics:
                    session.run("""
                        MATCH (q:Question {text: $q})
                        MERGE (top:Topic {name: $t})
                        MERGE (q)-[:ABOUT]->(top)
                    """, q=q, t=t)
                
                # Link Products
                for p in meta.products:
                    session.run("""
                        MATCH (q:Question {text: $q})
                        MERGE (prod:Product {name: $p})
                        MERGE (q)-[:RELATES_TO]->(prod)
                    """, q=q, p=p)
            
            print(f"  -> Linked: {len(meta.topics)} topics, {len(meta.products)} products")
            success_count += 1

        except Exception as e:
            print(f"  ⚠️ Meta extraction failed: {e}")

    print(f"\n✅ Ingestion Complete. Enriched {success_count}/{len(data)} items.")
    Neo4jManager.close()

if __name__ == "__main__":
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Ingest FAQ data into Neo4j with AI enrichment.")
    
    # We use -name to match your request, though --name is standard python convention.
    # argparse handles single dash if ambiguous args don't exist.
    parser.add_argument("-groq", type=str, help="Groq API Key for Metadata Extraction", default=os.getenv("GROQ_API_KEY"))
    parser.add_argument("-openrouter", type=str, help="OpenRouter API Key for Embeddings", default=os.getenv("OPENROUTER_API_KEY"))
    
    args = parser.parse_args()
    
    if not args.openrouter:
        print("❌ Error: OpenRouter API Key is required (pass via -openrouter or set OPENROUTER_API_KEY env var)")
        sys.exit(1)
        
    ingest_data(groq_key=args.groq, openrouter_key=args.openrouter)