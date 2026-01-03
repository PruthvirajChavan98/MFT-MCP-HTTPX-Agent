from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import create_react_agent

app = FastAPI()

# Request schema
class AgentRequest(BaseModel):
    session_id: str
    question: str

 # LLM setup
llm = AzureChatOpenAI(
    api_key="ddf",
    api_version="2025-03-01-preview",
    azure_deployment="GPT4",
    azure_endpoint="https://hfcl-genai-apim-cin-001-prod.azure-api.net",
    streaming=True
)

# connections = {
# "hero_fincorp": {
#     "url": "http://0.0.0.0:8050/sse",
#     "transport": "sse",
#     "headers": {
#         "X-Session-ID": request.session_id
#     }
# }
# }

# # Initialize client and tools
# client = MultiServerMCPClient(connections)
# tools = await client.get_tools()

@app.post("/agent/query")
async def query_agent(request: AgentRequest):
    try:
        # Set up dynamic headers and connections
        connections = {
            "hero_fincorp": {
                "url": "http://0.0.0.0:8050/sse",
                "transport": "sse",
                "headers": {
                    "X-Session-ID": request.session_id
                }
            }
        }

        # Initialize client and tools
        client = MultiServerMCPClient(connections)
        tools = await client.get_tools()

        print(tools)

        # Create ReAct agent
        agent = create_react_agent(
            model=llm,
            tools=tools,
        )

        # Ask the question
        response = await agent.ainvoke({
            "messages": [
                {"role": "user", "content": request.question}
            ]
        })

        return {"response": response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
