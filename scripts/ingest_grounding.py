import argparse
import json
import os
import sys

from langchain_openai import OpenAIEmbeddings

# Fix path to import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.neo4j_mgr import Neo4jManager


def get_embeddings_model(api_key: str):
    """Configures OpenAIEmbeddings to point to OpenRouter."""
    if not api_key:
        raise ValueError("OpenRouter API Key is required for embeddings.")

    return OpenAIEmbeddings(
        model="openai/text-embedding-3-small",
        api_key=api_key,  # type: ignore
        base_url="https://openrouter.ai/api/v1",
        check_embedding_ctx_length=False,
    )


def ingest_grounding_data(openrouter_key: str):
    # Reuse the same source data
    json_path = os.path.join("data", "hfcl_faq_data.json")
    if not os.path.exists(json_path):
        print(f"❌ File not found: {json_path}")
        return

    with open(json_path, "r") as f:
        data = json.load(f)

    driver = Neo4jManager.get_driver()

    try:
        embeddings = get_embeddings_model(openrouter_key)
    except ValueError as e:
        print(f"❌ Setup Error: {e}")
        return

    # 1. Setup Schema for Grounding Store
    with driver.session() as session:
        # Constraint: Ensure uniqueness on text to avoid duplicates
        session.run(
            "CREATE CONSTRAINT grounding_uniq IF NOT EXISTS FOR (g:GroundingQuestion) REQUIRE g.text IS UNIQUE"
        )

        # Index: Create the separate vector index
        print("🔧 Creating/Verifying 'grounding_embeddings' index...")
        session.run("""
            CREATE VECTOR INDEX grounding_embeddings IF NOT EXISTS
            FOR (g:GroundingQuestion)
            ON (g.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}
        """)

    print(f"🚀 Starting Grounding Ingestion of {len(data)} items...")
    success_count = 0

    for i, item in enumerate(data):
        q = item.get("question")
        # We only need the question text for grounding context
        if not q:
            continue

        print(f"Processing [{i+1}/{len(data)}]: {q[:40]}...")

        # 2. Generate Vector
        try:
            vector = embeddings.embed_query(q)
        except Exception as e:
            print(f"  ⚠️ Embedding failed: {e}")
            continue

        # 3. Ingest as GroundingQuestion
        # We store just the text and embedding. We don't necessarily need the Answer
        # or other metadata for this specific validation task, but storing it doesn't hurt.
        query_base = """
        MERGE (g:GroundingQuestion {text: $q})
        ON CREATE SET g.embedding = $vector
        ON MATCH SET g.embedding = $vector
        """

        try:
            Neo4jManager.execute_write(query_base, {"q": q, "vector": vector})
            success_count += 1
        except Exception as e:
            print(f"  ⚠️ DB Write failed: {e}")

    print(f"\n✅ Grounding Store Ready. Ingested {success_count}/{len(data)} items.")
    Neo4jManager.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest data into the Grounding Store.")
    parser.add_argument(
        "-openrouter", type=str, help="OpenRouter API Key", default=os.getenv("OPENROUTER_API_KEY")
    )

    args = parser.parse_args()

    if not args.openrouter:
        print(
            "❌ Error: OpenRouter API Key is required (pass via -openrouter or set OPENROUTER_API_KEY env var)"
        )
        sys.exit(1)

    ingest_grounding_data(openrouter_key=args.openrouter)
