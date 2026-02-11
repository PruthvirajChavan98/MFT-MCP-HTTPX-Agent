# POST /agent/stream — Full Request Lifecycle

## 1. Resolve Resources
```python
saved_config = config_manager.get_config(sid)          # Redis hash
model = get_llm(model_name, or_key, nv_key, ...)      # Provider routing
tools = mcp_manager.rebuild_tools_for_user(sid, or_key) # Auth-gated
```

## 2. Background Router (non-blocking)
```python
router_task = asyncio.create_task(nbfc_router_service.classify(question, ...))
```
Router result is for logging/eval only — does NOT influence the response.

## 3. Context Capture
- `agent.aget_state(thread_id=sid)` → chat history from Redis checkpoint
- `_get_app_id_for_session(sid)` → app_id from MCP session
- `ShadowEvalCollector(...)` initialized with system_prompt, chat_history, tool_definitions

## 4. KB-First Short-Circuit
```python
kb_payload = await kb_first_payload(question, tools)
# If regex matches: stream KB answer as 160-char chunks, skip LLM entirely
```

## 5. LangGraph ReAct Agent
```python
agent = create_react_agent(model=model, tools=tools, checkpointer=CHECKPOINTER)
async for event in agent.astream_events(inputs, config, version="v2"):
    # on_chat_model_stream → reasoning_token / token SSE
    # on_tool_start → tool_start SSE
    # on_tool_end → tool_end SSE (cleaned via _extract_tool_output)
```

## 6. Finalization (in `finally` block)
```python
router_out = await router_task            # Get router result
collector.set_router_outcome(router_out)  # Attach to trace
asyncio.create_task(maybe_shadow_eval_commit(collector))  # Fire-and-forget
```