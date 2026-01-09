import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.messages import SystemMessage, HumanMessage

# Import modularized components
from Loggers.StdOutLogger import StdoutLogger
from prompts import SYSTEM_PROMPT
from agent_config import REDIS_URL, PORT
from agent_schemas import AgentRequest
from agent_utils import valid_session_id
from agent_llm import llm
from agent_mcp import mcp_manager

# Import Redis Checkpointer
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

log = StdoutLogger(name="langchain_server")

# Globals
CHECKPOINTER: Optional[BaseCheckpointSaver] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global CHECKPOINTER
    log.info(f"STARTUP: Redis Checkpointer at {REDIS_URL}")
    
    # 1. Initialize Checkpointer
    async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
        CHECKPOINTER = checkpointer
        
        # 2. Initialize MCP Manager
        await mcp_manager.initialize()
        
        yield
        
        # 3. Cleanup
        await mcp_manager.shutdown()
        log.info("SHUTDOWN: Resources cleared")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/agent/query")
async def query_agent(request: AgentRequest):
    try:
        sid = valid_session_id(request.session_id)
        tools = mcp_manager.rebuild_tools_for_user(sid)
        
        if not tools:
            raise HTTPException(status_code=500, detail="No tools loaded")
        
        agent = create_react_agent(
            model=llm,
            tools=tools,
            checkpointer=CHECKPOINTER,          
        )

        inputs = {
            "messages": [
                SystemMessage(SYSTEM_PROMPT.strip()),
                HumanMessage(request.question),
            ]
        }
        
        resp = await agent.ainvoke(
            inputs,
            {"configurable": {"thread_id": sid}},
        )
        return {"response": resp}
    except Exception as e:
        log.error(f"Query Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/stream")
async def stream_agent(request: AgentRequest):
    sid = valid_session_id(request.session_id)
    tools = mcp_manager.rebuild_tools_for_user(sid)
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        checkpointer=CHECKPOINTER
    )

    inputs = {
        "messages": [
            SystemMessage(SYSTEM_PROMPT.strip()),
            HumanMessage(request.question),
        ]
    }
    
    async def event_generator():
        try:
            async for event in agent.astream_events(
                inputs, 
                {"configurable": {"thread_id": sid}}, 
                version="v2"
            ):
                kind = event["event"]

                # 1. Stream Tokens
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"] # type: ignore
                    
                    # Reasoning
                    reasoning = chunk.additional_kwargs.get("reasoning_content")
                    if reasoning:
                        yield {"event": "reasoning_token", "data": reasoning}
                        continue 

                    # Content
                    if chunk.content:
                        yield {"event": "token", "data": chunk.content}

                # 2. Tool Calls
                elif kind == "on_tool_start":
                    if event["name"] not in ["_Exception"]: 
                        tool_info = {
                            "tool": event["name"],
                            "input": event["data"].get("input")
                        }
                        yield {"event": "tool_start", "data": json.dumps(tool_info)}

                # 3. Tool Output
                elif kind == "on_tool_end":
                     yield {"event": "tool_end", "data": str(event["data"].get("output"))}

            yield {"event": "done", "data": "[DONE]"}

        except Exception as e:
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(
        event_generator(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)