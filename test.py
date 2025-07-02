# # session_store.py

# import sqlite3
# import json
# from typing import Optional


# class SessionStore:
#     def __init__(self, db_path: str = "session_store.db"):
#         self.conn = sqlite3.connect(db_path, check_same_thread=False)
#         self._create_table()

#     def _create_table(self):
#         with self.conn:
#             self.conn.execute("""
#                 CREATE TABLE IF NOT EXISTS sessions (
#                     session_id TEXT PRIMARY KEY,
#                     data TEXT NOT NULL
#                 )
#             """)

#     def set(self, session_id: str, data: dict):
#         with self.conn:
#             self.conn.execute("""
#                 INSERT INTO sessions (session_id, data)
#                 VALUES (?, ?)
#                 ON CONFLICT(session_id) DO UPDATE SET data=excluded.data
#             """, (session_id, json.dumps(data)))

#     def get(self, session_id: str) -> Optional[dict]:
#         cursor = self.conn.execute("""
#             SELECT data FROM sessions WHERE session_id = ?
#         """, (session_id,))
#         row = cursor.fetchone()
#         return json.loads(row[0]) if row else None

#     def update(self, session_id: str, updates: dict):
#         current_data = self.get(session_id) or {}
#         current_data.update(updates)
#         self.set(session_id, current_data)

#     def delete(self, session_id: str):
#         with self.conn:
#             self.conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

#     def close(self):
#         self.conn.close()


# # HFCLAPIs.py:

# import httpx
# from Loggers.StdOutLogger import StdoutLogger
# from session_store import SessionStore

# # Instantiate session store (ideally shared instance across app)
# session_store = SessionStore()

# class HeroFincorpAPIs:
#     def __init__(self, session_id):
#         self.session_id = session_id
#         self.logger = StdoutLogger()
#         self.base_url = "https://herokuapi-dev.herofincorp.com"

#         # Load session data
#         session_data = session_store.get(session_id)
#         if not session_data:
#             raise ValueError(f"No session found for session_id: {session_id}")

#         self.bearer_token = session_data.get("access_token")
#         self.app_id = session_data.get("app_id")

#         if not self.bearer_token:
#             raise ValueError("Access token missing in session data")

#     def _create_headers(self):
#         return {
#             "Authorization": f"Bearer {self.bearer_token}",
#             "Content-Type": "application/json"
#         }

#     def _handle_response(self, response: httpx.Response):
#         if response.status_code in [200, 201, 208]:
#             return response.json()
#         return {
#             "status_code": response.status_code,
#             "error": response.text
#         }

#     def _request(self, method, endpoint, headers=None, json=None):
#         url = f"{self.base_url}{endpoint}"
#         try:
#             with httpx.Client() as client:
#                 response = client.request(method, url, headers=headers, json=json)
#                 self.logger.info(f"{method} {url} - {response.status_code}: {response.text}")
#                 return self._handle_response(response)
#         except httpx.RequestError as e:
#             self.logger.error(f"HTTP error occurred: {e}")
#             return {"error": str(e)}
#         except Exception as e:
#             self.logger.error(f"An error occurred: {e}")
#             return {"error": str(e)}

#     def get_dashboard_data(self):
#         return self._request("GET", "/herofin-service/home/", headers=self._create_headers())

#     def get_loan_details(self):
#         if not self.app_id:
#             return {"error": "App ID missing in session"}
#         return self._request("GET", f"/herofin-service/loan/details/{self.app_id}/", headers=self._create_headers())

#     def get_overdue_details(self):
#         if not self.app_id:
#             return {"error": "App ID missing in session"}
#         return self._request("GET", f"/herofin-service/loan_overdues/{self.app_id}/", headers=self._create_headers())

#     def get_repayment_schedule(self):
#         return self._request("GET", "/herofin-service/download/repayment-schedule", headers=self._create_headers())

#     def get_foreclosure_details(self):
#         if not self.app_id:
#             return {"error": "App ID missing in session"}
#         return self._request("GET", f"/herofin-service/loan/foreclosuredetails/{self.app_id}/", headers=self._create_headers())

#     def download_noc_letter(self):
#         return self._request("POST", "/herofin-service/download/noc-letter/", headers=self._create_headers())

#     def make_noc_request(self, chassis_no: str, engine_no: str, vehicle_number: str, bike_rc_image_base_64: str):
#         """
#         Updates the bike profile for the user (NOC flow).

#         Args:
#             chassis_no (str): Chassis number of the bike
#             engine_no (str): Engine number of the bike
#             vehicle_number (str): Vehicle registration number
#             bike_rc_image_url (str): Image URL or base64 representation of the RC

#         Returns:
#             dict: API response
#         """
#         payload = {
#             "case_type": "noc",
#             "chassis_no": chassis_no,
#             "engine_no": engine_no,
#             "vehicle_number": vehicle_number,
#             "bike_rc": [
#                 {
#                     "imageUrl": bike_rc_image_base_64
#                 }
#             ],
#             "file_name": f"{self.app_id}_{self.session_id}.jpg"
#         }
#         return self._request(
#             "PUT",
#             "/herofin-service/profiles/?update=bike",
#             headers=self._create_headers(),
#             json=payload
#         )
    

# # MCP_server.py

# from fastmcp import FastMCP
# from fastapi import Request
# from fastmcp import FastMCP
# from fastmcp.server.dependencies import get_http_request

# from HFCL_Auth_APIs import HeroFincorpAuthAPIs
# from HFCLAPIsNew import HeroFincorpAPIs

# mcp = FastMCP(name="HFCL MCP Server httpx tools")

# def extract_custom_headers():
#     """
#     Extracts custom headers 'X-Bearer-Token' and 'X-App-ID' from an HTTP request.

#     Parameters:
#         request (Request): FastAPI request object

#     Returns:
#         dict: Dictionary containing bearer_token and app_id
#     """

#     request : Request = get_http_request()
#     session_id = request.headers.get("X-Session-ID", "")

#     return session_id


# def get_auth_api_client() -> HeroFincorpAuthAPIs:
#     """Initialize and return HeroFincorpAuthAPIs client using headers from request."""
#     session_id = extract_custom_headers()
#     return HeroFincorpAuthAPIs(session_id)


# def get_api_client() -> HeroFincorpAPIs:
#     """Initialize and return HeroFincorpAPIs client using headers from request."""
#     session_id = extract_custom_headers()
#     return HeroFincorpAPIs(session_id)


# @mcp.tool
# def generate_otp(user_input: str) -> dict:
#     """
#     Generate OTP using Hero Fincorp Auth APIs, Helps user to login
#     - ONLY 1 of these needed:
#         5-8 digit app id or 10 digit Mobile Number in arguments
#     """
#     try:
#         auth_api = get_auth_api_client()
#         return auth_api.generate_otp(user_input)
#     except Exception as e:
#         return {"error": f"Failed to generate OTP: {str(e)}"}

# @mcp.tool
# def validate_otp(otp: str) -> dict:
#     """
#     Verify OTP using Hero Fincorp Auth APIs, Helps user to login
#     - TO BE CALLED AFTER 'generate_otp'
#     """
#     try:
#         auth_api = get_auth_api_client()
#         return auth_api.validate_otp(otp)
#     except Exception as e:
#         return {"error": f"Failed to verify OTP: {str(e)}"}
    

# @mcp.tool
# def get_dashboard_data() -> dict:
#     """Get dashboard data from Hero Fincorp API"""
#     try:
#         api = get_api_client()
#         return api.get_dashboard_data()
#     except Exception as e:
#         return {"error": f"Failed to get dashboard data: {str(e)}"}


# @mcp.tool
# def get_loan_details() -> dict:
#     """Get loan details from Hero Fincorp API"""
#     try:
#         api = get_api_client()
#         return api.get_loan_details()
#     except Exception as e:
#         return {"error": f"Failed to get loan details: {str(e)}"}


# @mcp.tool
# def get_overdue_details() -> dict:
#     """Get overdue details from Hero Fincorp API"""
#     try:
#         api = get_api_client()
#         return api.get_overdue_details()
#     except Exception as e:
#         return {"error": f"Failed to get overdue details: {str(e)}"}


# @mcp.tool
# def get_repayment_schedule() -> dict:
#     """Get repayment schedule from Hero Fincorp API"""
#     try:
#         api = get_api_client()
#         return api.get_repayment_schedule()
#     except Exception as e:
#         return {"error": f"Failed to get repayment schedule: {str(e)}"}


# @mcp.tool
# def get_foreclosure_details() -> dict:
#     """Get foreclosure details from Hero Fincorp API"""
#     try:
#         api = get_api_client()
#         return api.get_foreclosure_details()
#     except Exception as e:
#         return {"error": f"Failed to get foreclosure details: {str(e)}"}


# @mcp.tool
# def upload_noc_documents(chassis_number: str, engine_no: str, vehicle_number: str, bike_rc_image_base64_string: str) -> dict:
#     """
#         makes Noc request for vehicle (NOC flow).

#         Args:
#             chassis_no (str): Chassis number of the bike
#             engine_no (str): Engine number of the bike
#             vehicle_number (str): Vehicle registration number
#             bike_rc_image_url (str): Image URL or base64 representation of the RC

#         Returns:
#             dict: API response
#         """
#     try:
#         api = get_api_client()
#         return api.make_noc_request(
#             chassis_no=chassis_number,
#             engine_no=engine_no,
#             vehicle_number=vehicle_number,
#             bike_rc_image_base_64=bike_rc_image_base64_string
#         )
#     except Exception as e:
#         return {"error": f"Failed to upload NOC documents: {str(e)}"}


# @mcp.tool
# def download_noc_letter() -> dict:
#     """Download NOC letter from Hero Fincorp API"""
#     try:
#         api = get_api_client()
#         return api.download_noc_letter()
#     except Exception as e:
#         return {"error": f"Failed to download NOC letter: {str(e)}"}


# # Start the FastMCP server
# if __name__ == "__main__":
#     mcp.run(transport="sse", host="0.0.0.0", port=8050)


# # MCP_client.py:

# from langchain_mcp_adapters.client import MultiServerMCPClient

# class MCPToolService:
#     def __init__(self, session_id: str):
#         self.connections = {
#             "hero_fincorp": {
#                 "url": "http://0.0.0.0:8050/sse",
#                 "transport": "sse",
#                 "headers": {
#                     "X-Session-ID": session_id
#                 }
#             }
#         }

#     async def get_tools(self):
#         client = MultiServerMCPClient(self.connections)
#         tools = await client.get_tools()
#         return tools
    

# # AgentHandle.py

# import aiosqlite
# from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
# from langgraph.prebuilt import create_react_agent

# from azure_llm import LLMService

# class AgentHandler:
#     def __init__(self, tools, session_id: str):
#         self.tools = tools
#         self.session_id = session_id
#         self.llm = LLMService().get_llm()
#         self.agent = None
#         self.config = {"configurable": {"thread_id": self.session_id}}
#         self.conn = None  # persistent connection

#     async def initialize(self):
#         self.conn = await aiosqlite.connect("checkpoints.db")
#         checkpointer = AsyncSqliteSaver(self.conn)
#         self.agent = create_react_agent(
#             model=self.llm,
#             tools=self.tools,
#             checkpointer=checkpointer
#         )

#     async def ask(self, question: str):
#         if self.agent is None:
#             await self.initialize()
#         response = await self.agent.ainvoke(
#             {"messages": [{"role": "user", "content": question}]},
#             config=self.config
#         )
#         return response

#     async def ask_stream(self, question: str):
#         if self.agent is None:
#             await self.initialize()

#         async for stream_mode, chunk in self.agent.astream(
#             {"messages": [{"role": "user", "content": question}]},
#             config=self.config,
#             stream_mode=["updates", "messages", "custom"]
#         ):
#             if stream_mode == "messages" and hasattr(chunk[0], "content"):
#                 yield chunk[0].content


#     async def ask_astream_events(self, question: str):
#         if self.agent is None:
#             await self.initialize()
#         async for event in self.agent.astream_events(
#             {"messages": [{"role": "user", "content": question}]},
#             config=self.config,
#             version="v1"
#         ):
#             if (
#                 event.get("event") == "on_chat_model_stream" and 
#                 event.get("metadata", {}).get("langgraph_node") == "agent"
#             ):
#                 chunk_content = event["data"]["chunk"].content
#                 yield chunk_content


# # azure_llm.py

# from langchain_openai import AzureChatOpenAI

# class LLMService:
#     def __init__(self):
#         self.llm = AzureChatOpenAI(
#             api_key="27QdNmH3G7rRgh4sJ94LeEIy18nk2vd6LMb4rP7ap1onYRvSpEC7JQQJ99BFACHYHv6XJ3w3AAAAACOGpeqv",
#             api_version="2025-03-01-preview",
#             azure_deployment="gpt-4o",
#             azure_endpoint="https://chava-mc1n6r47-eastus2.cognitiveservices.azure.com/",
#             streaming=True
#         )

#     def get_llm(self):
#         return self.llm
    

# # main.py

# from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
# from fastapi.responses import StreamingResponse
# import os

# from schemas import AgentRequest
# from mcp_client import MCPToolService
# from agent_handler import AgentHandler


# app = FastAPI()

# os.environ["LANGSMITH_TRACING"] = "true"
# os.environ["LANGSMITH_API_KEY"] = "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"
# os.environ["LANGSMITH_PROJECT"] = "LangGraph-MCP-Client"

# @app.get("/")
# def read_root():
#     return {"message": "Hello from FastAPI"}


# @app.post("/agent/query")
# async def query_agent(request: AgentRequest):
#     try:
#         mcp_service = MCPToolService(request.session_id)
#         tools = await mcp_service.get_tools()

#         agent_handler = AgentHandler(tools, request.session_id)
#         response = await agent_handler.ask(request.question)

#         return {"response": response}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @app.post("/agent/query/stream")
# async def query_agent_stream(request: AgentRequest):
#     try:
#         mcp_service = MCPToolService(request.session_id)
#         tools = await mcp_service.get_tools()

#         agent_handler = AgentHandler(tools, request.session_id)

#         async def stream_response():
#             async for content in agent_handler.ask_stream(request.question):
#                 # SSE format: data: <content>\n\n
#                 yield f"data: {content}\n\n"

#         return StreamingResponse(stream_response(), media_type="text/event-stream")

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @app.post("/agent/query/stream-events")
# async def query_agent_stream_events(request: AgentRequest):
#     try:
#         mcp_service = MCPToolService(request.session_id)
#         tools = await mcp_service.get_tools()

#         agent_handler = AgentHandler(tools, request.session_id)

#         async def stream_response():
#             async for content in agent_handler.ask_astream_events(request.question):
#                 # SSE format: data: <content>\n\n
#                 yield f"data: {content}\n\n"

#         return StreamingResponse(stream_response(), media_type="text/event-stream")

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
    

# @app.websocket("/ws/agent/query/stream")
# async def websocket_query_agent_stream(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         # Receive the first message as JSON: { "bearer_token": "...", "app_id": "...", "thread_id": "...", "question": "..." }
#         data = await websocket.receive_json()

#         mcp_service = MCPToolService(data["session_id"])
#         tools = await mcp_service.get_tools()

#         agent_handler = AgentHandler(tools, data["session_id"])

#         async for content in agent_handler.ask_stream(data["question"]):
#             await websocket.send_text(content)

#         await websocket.send_text("[DONE]")
#         await websocket.close()

#     except WebSocketDisconnect:
#         print("WebSocket disconnected")

#     except Exception as e:
#         await websocket.send_text(f"[ERROR] {str(e)}")
#         await websocket.close()


# @app.websocket("/ws/agent/query/stream-events")
# async def websocket_query_agent_stream_events(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         # Receive the first message as JSON
#         data = await websocket.receive_json()

#         mcp_service = MCPToolService(data["session_id"])
#         tools = await mcp_service.get_tools()

#         agent_handler = AgentHandler(tools, data["session_id"])

#         async for content in agent_handler.ask_astream_events(data["question"]):
#             await websocket.send_text(content)

#         await websocket.send_text("[DONE]")
#         await websocket.close()

#     except WebSocketDisconnect:
#         print("WebSocket disconnected")

#     except Exception as e:
#         await websocket.send_text(f"[ERROR] {str(e)}")
#         await websocket.close()