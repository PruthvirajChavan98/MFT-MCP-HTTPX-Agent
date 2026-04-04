"""Manual LangGraph Recursive RAG workflow using message-based state."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.agent_service.tools.tool_execution_policy import (
    build_same_turn_dedupe_key,
    get_tool_execution_policy,
)

log = logging.getLogger(__name__)


class RecursiveRAGState(TypedDict):
    """Strict message-based state for recursive tool-assisted generation."""

    messages: Annotated[list, add_messages]
    iteration: int
    max_iterations: int
    tool_execution_cache: dict[str, str]


def _safe_tool_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "content"):
        content = getattr(value, "content", "")
        return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_recursive_rag_graph(
    *,
    model: Any,
    tools: list[Any],
    system_prompt: str,
    checkpointer: Any,
):
    """
    Build strict recursive RAG graph with manual StateGraph construction.

    State is message-based; retrieval context flows only through message objects.
    """

    tools_by_name = {getattr(tool, "name", ""): tool for tool in tools}
    llm = model.bind_tools(tools) if tools else model

    async def llm_step(state: RecursiveRAGState) -> dict[str, Any]:
        messages = state.get("messages", [])
        model_messages = [SystemMessage(content=system_prompt), *messages]

        ai_message = await llm.ainvoke(model_messages)
        if not isinstance(ai_message, AIMessage):
            ai_message = AIMessage(content=str(ai_message))

        return {"messages": [ai_message]}

    async def run_tools(state: RecursiveRAGState) -> dict[str, Any]:
        messages = state.get("messages", [])
        if not messages:
            return {
                "iteration": state.get("iteration", 0),
                "tool_execution_cache": dict(state.get("tool_execution_cache", {}) or {}),
            }

        last_message = messages[-1]
        if not isinstance(last_message, AIMessage):
            return {
                "iteration": state.get("iteration", 0),
                "tool_execution_cache": dict(state.get("tool_execution_cache", {}) or {}),
            }

        tool_calls = getattr(last_message, "tool_calls", []) or []
        if not tool_calls:
            return {
                "iteration": state.get("iteration", 0),
                "tool_execution_cache": dict(state.get("tool_execution_cache", {}) or {}),
            }

        tool_messages: list[ToolMessage] = []
        tool_execution_cache = dict(state.get("tool_execution_cache", {}) or {})
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {}) or {}
            if not isinstance(tool_args, dict):
                tool_args = {"input": tool_args}
            tool_call_id = tool_call.get("id") or tool_name or "tool-call"
            policy = get_tool_execution_policy(tool_name)
            dedupe_key = (
                build_same_turn_dedupe_key(tool_name, tool_args)
                if policy.same_turn_dedupe
                else None
            )

            tool = tools_by_name.get(tool_name)
            if tool is None:
                tool_messages.append(
                    ToolMessage(
                        content=f"Tool '{tool_name}' is not available.",
                        tool_call_id=tool_call_id,
                        name=tool_name,
                    )
                )
                continue

            if dedupe_key and dedupe_key in tool_execution_cache:
                content = tool_execution_cache[dedupe_key]
                log.info(
                    "Suppressing duplicate side-effect tool call within run tool=%s dedupe_key=%s",
                    tool_name,
                    dedupe_key,
                )
            else:
                try:
                    result = await tool.ainvoke(tool_args)
                    content = _safe_tool_output(result)
                except Exception as exc:
                    log.warning("Tool invocation failed for %s: %r", tool_name, exc)
                    content = f"Tool '{tool_name}' failed: {exc}"
                if dedupe_key:
                    tool_execution_cache[dedupe_key] = content

            tool_messages.append(
                ToolMessage(content=content, tool_call_id=tool_call_id, name=tool_name)
            )

        return {
            "messages": tool_messages,
            "iteration": state.get("iteration", 0) + 1,
            "tool_execution_cache": tool_execution_cache,
        }

    def route_after_llm(state: RecursiveRAGState) -> Literal["run_tools", "__end__"]:
        messages = state.get("messages", [])
        if not messages:
            return END

        last_message = messages[-1]
        if not isinstance(last_message, AIMessage):
            return END

        has_tool_calls = bool(getattr(last_message, "tool_calls", []) or [])
        if not has_tool_calls:
            return END

        iteration = state.get("iteration", 0)
        max_iterations = state.get("max_iterations", 6)
        if iteration >= max_iterations:
            return END

        return "run_tools"

    builder = StateGraph(RecursiveRAGState)
    builder.add_node("llm_step", llm_step)
    builder.add_node("run_tools", run_tools)

    builder.add_edge(START, "llm_step")
    builder.add_conditional_edges("llm_step", route_after_llm)
    builder.add_edge("run_tools", "llm_step")

    return builder.compile(checkpointer=checkpointer)


def initial_recursive_rag_state(question: str, *, max_iterations: int = 6) -> RecursiveRAGState:
    """Build initial state for graph invocation."""
    return {
        "messages": [HumanMessage(content=question)],
        "iteration": 0,
        "max_iterations": max_iterations,
        "tool_execution_cache": {},
    }
