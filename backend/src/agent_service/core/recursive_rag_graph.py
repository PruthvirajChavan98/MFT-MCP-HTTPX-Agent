"""LangGraph Recursive RAG workflow using message-based state."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

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


class DedupToolNode:
    """Graph node that executes tool calls with same-turn deduplication.

    Encapsulates tool lookup, execution-policy-driven deduplication, and safe
    output formatting into a single callable that plugs into a LangGraph
    StateGraph as ``builder.add_node("run_tools", DedupToolNode(tools))``.
    """

    def __init__(self, tools: list[Any]) -> None:
        self._tools_by_name = {getattr(tool, "name", ""): tool for tool in tools}

    async def __call__(self, state: RecursiveRAGState) -> dict[str, Any]:
        messages = state.get("messages", [])
        cache = dict(state.get("tool_execution_cache", {}) or {})
        iteration = state.get("iteration", 0)

        if not messages or not isinstance(messages[-1], AIMessage):
            return {"iteration": iteration, "tool_execution_cache": cache}

        tool_calls = getattr(messages[-1], "tool_calls", []) or []
        if not tool_calls:
            return {"iteration": iteration, "tool_execution_cache": cache}

        tool_messages: list[ToolMessage] = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {}) or {}
            if not isinstance(tool_args, dict):
                tool_args = {"input": tool_args}
            tool_call_id = tool_call.get("id") or tool_name or "tool-call"

            tool = self._tools_by_name.get(tool_name)
            if tool is None:
                tool_messages.append(
                    ToolMessage(
                        content=f"Tool '{tool_name}' is not available.",
                        tool_call_id=tool_call_id,
                        name=tool_name,
                    )
                )
                continue

            content = self._execute_with_dedupe(tool_name, tool_args, tool_call_id, tool, cache)
            if content is None:
                # Not cached — must await actual execution
                content = await self._invoke_tool(tool_name, tool_args, tool, cache)

            tool_messages.append(
                ToolMessage(content=content, tool_call_id=tool_call_id, name=tool_name)
            )

        return {
            "messages": tool_messages,
            "iteration": iteration + 1,
            "tool_execution_cache": cache,
        }

    def _execute_with_dedupe(
        self,
        tool_name: str,
        tool_args: dict,
        tool_call_id: str,
        tool: Any,
        cache: dict[str, str],
    ) -> str | None:
        """Return cached result if this is a duplicate side-effect call, else None."""
        policy = get_tool_execution_policy(tool_name)
        if not policy.same_turn_dedupe:
            return None

        dedupe_key = build_same_turn_dedupe_key(tool_name, tool_args)
        if dedupe_key and dedupe_key in cache:
            log.info(
                "Suppressing duplicate side-effect tool call within run tool=%s dedupe_key=%s",
                tool_name,
                dedupe_key,
            )
            return cache[dedupe_key]
        return None

    async def _invoke_tool(
        self,
        tool_name: str,
        tool_args: dict,
        tool: Any,
        cache: dict[str, str],
    ) -> str:
        """Invoke tool, cache result if policy requires dedup, return formatted output."""
        policy = get_tool_execution_policy(tool_name)
        dedupe_key = (
            build_same_turn_dedupe_key(tool_name, tool_args) if policy.same_turn_dedupe else None
        )

        try:
            result = await tool.ainvoke(tool_args)
            content = _safe_tool_output(result)
        except Exception as exc:
            log.warning("Tool invocation failed for %s: %r", tool_name, exc)
            content = f"Tool '{tool_name}' failed: {exc}"

        if dedupe_key:
            cache[dedupe_key] = content
        return content


def build_recursive_rag_graph(
    *,
    model: Any,
    tools: list[Any],
    system_prompt: str,
    checkpointer: Any,
):
    """Build recursive RAG graph with DedupToolNode for tool execution."""

    llm = model.bind_tools(tools) if tools else model

    async def llm_step(state: RecursiveRAGState) -> dict[str, Any]:
        messages = state.get("messages", [])
        model_messages = [SystemMessage(content=system_prompt), *messages]

        ai_message = await llm.ainvoke(model_messages)
        if not isinstance(ai_message, AIMessage):
            ai_message = AIMessage(content=str(ai_message))

        return {"messages": [ai_message]}

    def route_after_llm(state: RecursiveRAGState) -> str:
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
    builder.add_node("run_tools", DedupToolNode(tools))

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
