# import os
# from typing import Optional, Type
# from pydantic import BaseModel, Field
# from langchain_core.tools import StructuredTool
# from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
# from langchain_groq import ChatGroq
# from langchain_core.prompts import PromptTemplate

# # FIX: Import config constants to ensure consistency with main agent
# from src.agent_service.config import GROQ_API_KEY, GROQ_BASE_URL

# # --- 1. Define Input Schema ---
# class GraphQueryInput(BaseModel):
#     """Input for the Hero Fincorp Graph Tool."""
#     query: str = Field(
#         description="A natural language question about Hero Fincorp loans, processes, or products. "
#                     "Example: 'What is the foreclosure process?' or 'Tell me about HIPL'."
#     )

# # --- 2. Singleton Chain Holder ---
# class GraphChainSingleton:
#     _instance: Optional[GraphCypherQAChain] = None

#     @classmethod
#     def get_chain(cls) -> GraphCypherQAChain:
#         if cls._instance is None:
#             # Initialize Graph Connection
#             graph = Neo4jGraph(
#                 url=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
#                 username=os.getenv("NEO4J_USER", "neo4j"),
#                 password=os.getenv("NEO4J_PASSWORD", "password")
#             )
#             graph.refresh_schema()

#             # Initialize LLM
#             # FIX: Use GROQ_BASE_URL from config (https://api.groq.com)
#             # instead of hardcoding the full path which causes duplication
#             llm = ChatGroq(
#                 api_key=GROQ_API_KEY, 
#                 base_url="https://api.groq.com", 
#                 model="openai/gpt-oss-120b", 
#                 temperature=0.0
#             )

#             # Define Schema-Aware Prompt
#             cypher_template = """
#             Task: Generate Cypher statement to query the Hero Fincorp Knowledge Graph.
#             Schema:
#             {schema}
            
#             Instructions:
#             1. Product Queries: MATCH (p:Product)<-[:RELATES_TO]-(q:Question)-[:HAS_ANSWER]->(a:Answer) WHERE p.name CONTAINS 'keyword'
#             2. Topic Queries: MATCH (t:Topic)<-[:ABOUT]-(q:Question)-[:HAS_ANSWER]->(a:Answer) WHERE t.name CONTAINS 'keyword'
#             3. General: MATCH (q:Question)-[:HAS_ANSWER]->(a:Answer) WHERE q.text CONTAINS 'keyword'
            
#             The question is:
#             {question}
#             """
            
#             prompt = PromptTemplate(
#                 input_variables=["schema", "question"], 
#                 template=cypher_template
#             )

#             cls._instance = GraphCypherQAChain.from_llm(
#                 llm,
#                 graph=graph,
#                 verbose=True,
#                 cypher_prompt=prompt,
#                 allow_dangerous_requests=True
#             )
#             print("✅ Connected to Neo4j Graph Chain.")
            
#         return cls._instance

# # --- 3. The Function Implementation ---
# def query_hero_fincorp(query: str) -> str:
#     """
#     Executes a natural language query against the Hero Fincorp Knowledge Graph.
#     """
#     chain = GraphChainSingleton.get_chain()
#     try:
#         response = chain.invoke({"query": query})
#         return response.get('result', "No result found.")
#     except Exception as e:
#         return f"Error querying graph: {str(e)}"

# # --- 4. The Factory Function ---
# def create_graph_tool() -> StructuredTool:
#     """
#     Returns a configured StructuredTool for the Graph.
#     """
#     return StructuredTool.from_function(
#         func=query_hero_fincorp,
#         name="hero_fincorp_knowledge_base",
#         description=(
#             "Useful for answering questions about Hero Fincorp financial products, "
#             "loan eligibility, foreclosure processes, insurance claims, and contact details. "
#             "Use this tool whenever the user asks about specific banking rules or loan types."
#         ),
#         args_schema=GraphQueryInput
#     )


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