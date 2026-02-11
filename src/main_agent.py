import logging
from fastapi import FastAPI, Depends, HTTPException
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

# Common BYOK Components
from src.common.security import get_byok_credentials
from src.common.factory import get_byok_llm, get_byok_embeddings
from src.common.neo4j_mgr import Neo4jManager

# Business Logic
from src.agent_service.features.nbfc_router import nbfc_router_service
from src.agent_service.core.agent_builder import build_byok_agent
from src.agent_service.core.schemas import AgentRequest
from src.agent_service.core.config import REDIS_URL, SYSTEM_PROMPT
from src.agent_service.tools.mcp_manager import mcp_manager

app = FastAPI()
log = logging.getLogger("agent_main")

# Initialize Redis Checkpointer for LangGraph
checkpointer = AsyncRedisSaver.from_conn_string(REDIS_URL)

@app.post("/agent/stream")
async def stream_agent(
    request: AgentRequest, 
    creds: dict = Depends(get_byok_credentials)
):
    """
    Production BYOK Request Lifecycle:
    1. Resolve Credentials (via Depends)
    2. Instantiate Model/Embeddings (via Factory)
    3. Run Operational Router
    4. Build and Execute Agent Graph
    """
    try:
        # 1. Instantiate BYOK Resources
        llm = get_byok_llm(
            model=request.model_name or "openai:gpt-4o", 
            api_key=creds["openai"] or creds["groq"] or creds["nvidia"],
            streaming=True
        )
        
        embeddings = get_byok_embeddings(
            model="text-embedding-3-small",
            api_key=creds["openai"]
        )

        # 2. Build Tools (Injecting BYOK info)
        tools = mcp_manager.rebuild_tools_for_user(
            request.session_id, 
            openrouter_api_key=creds["openai"]
        )

        # 3. Operations Routing (Pre-computation)
        router_out = await nbfc_router_service.classify_hybrid(
            text=request.question,
            llm=llm,
            embeddings=embeddings
        )

        # 4. Agent Execution
        agent = build_byok_agent(
            model=llm,
            tools=tools,
            checkpointer=checkpointer,
            system_prompt=SYSTEM_PROMPT
        )

        # Configuration for LangGraph persistence
        config = {"configurable": {"thread_id": request.session_id}}
        inputs = {"messages": [("human", request.question)]}
        
        # Invoke (or astream_events for true streaming)
        result = await agent.ainvoke(inputs, config=config)

        return {
            "response": result["messages"][-1].content,
            "router": router_out,
            "session_id": request.session_id
        }

    except Exception as e:
        log.error(f"Execution Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
