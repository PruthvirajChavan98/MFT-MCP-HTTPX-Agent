"""
Streaming Utilities and Tool Output Extraction
Handles SSE event generation, tool output parsing, and streaming state management.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


@dataclass
class StreamingState:
    """Tracks streaming session state and cumulative metrics."""

    total_cost: float = 0.0
    cumulative_usage: Dict[str, int] = field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "reasoning_tokens": 0,
            "cached_tokens": 0,
        }
    )


class StreamingUtils:
    """Utilities for managing streaming state, events, and tool outputs."""

    @staticmethod
    def extract_tool_output(output: Any) -> str:
        """Extract clean content from LangGraph/LangChain tool outputs."""
        if output is None:
            return ""

        # ToolMessage / BaseMessage-like objects
        if hasattr(output, "content"):
            content = getattr(output, "content", "")
            return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)

        # Dict wrapper with content key
        if isinstance(output, dict):
            if "content" in output:
                content = output["content"]
                return (
                    content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                )

            # Sometimes wrapped in messages list
            msgs = output.get("messages")
            if isinstance(msgs, list):
                for msg in reversed(msgs):
                    if hasattr(msg, "content"):
                        content = getattr(msg, "content", "")
                        return (
                            content
                            if isinstance(content, str)
                            else json.dumps(content, ensure_ascii=False)
                        )
                    if isinstance(msg, str):
                        return msg

            return json.dumps(output, ensure_ascii=False)

        # List of messages
        if isinstance(output, list):
            for msg in reversed(output):
                if hasattr(msg, "content"):
                    content = getattr(msg, "content", "")
                    return (
                        content
                        if isinstance(content, str)
                        else json.dumps(content, ensure_ascii=False)
                    )
                if isinstance(msg, str):
                    return msg
            return json.dumps(output, ensure_ascii=False)

        return str(output)

    @staticmethod
    def extract_reasoning_tokens(usage_metadata: Any) -> int:
        """
        Extract reasoning tokens from various usage metadata formats.

        Supports:
        - LangChain UsageMetadata with output_token_details.reasoning
        - Groq API format with direct reasoning_tokens field
        - OpenRouter format with reasoning_tokens
        - Dict format with nested output_token_details
        """
        reasoning_tokens = 0

        try:
            # LangChain standard: output_token_details.reasoning
            if hasattr(usage_metadata, "output_token_details"):
                details = getattr(usage_metadata, "output_token_details", None)
                if isinstance(details, dict):
                    reasoning_tokens = details.get("reasoning", 0)
                elif hasattr(details, "reasoning"):
                    reasoning_tokens = getattr(details, "reasoning", 0)

            # Direct reasoning_tokens field (Groq/OpenRouter)
            if not reasoning_tokens:
                if hasattr(usage_metadata, "reasoning_tokens"):
                    reasoning_tokens = getattr(usage_metadata, "reasoning_tokens", 0)
                elif isinstance(usage_metadata, dict):
                    reasoning_tokens = usage_metadata.get("reasoning_tokens", 0)

                    # Check nested output_token_details in dict
                    if not reasoning_tokens:
                        output_details = usage_metadata.get("output_token_details", {})
                        if isinstance(output_details, dict):
                            reasoning_tokens = output_details.get("reasoning", 0)
        except Exception as e:
            log.debug(f"Could not extract reasoning tokens: {e}")

        return int(reasoning_tokens) if reasoning_tokens else 0

    @staticmethod
    def accumulate_usage(state: StreamingState, usage_metadata: Any) -> None:
        """
        Accumulate token usage metrics from LLM responses.

        Handles multiple formats:
        - LangChain UsageMetadata objects
        - Dict format from various providers
        - Reasoning tokens from o1/o3/gpt-oss models
        """
        try:
            # Convert to dict if it's an object
            if hasattr(usage_metadata, "__dict__"):
                usage_dict = usage_metadata.__dict__
            elif isinstance(usage_metadata, dict):
                usage_dict = usage_metadata
            else:
                log.warning(f"Unknown usage_metadata format: {type(usage_metadata)}")
                return

            # Prompt/Input tokens
            prompt_tokens = usage_dict.get("input_tokens", 0) or usage_dict.get("prompt_tokens", 0)
            state.cumulative_usage["prompt_tokens"] += prompt_tokens

            # Completion/Output tokens
            completion_tokens = usage_dict.get("output_tokens", 0) or usage_dict.get(
                "completion_tokens", 0
            )
            state.cumulative_usage["completion_tokens"] += completion_tokens

            # Total tokens
            total_tokens = usage_dict.get("total_tokens", 0)
            if not total_tokens:
                total_tokens = prompt_tokens + completion_tokens
            state.cumulative_usage["total_tokens"] += total_tokens

            # ✅ Reasoning tokens (o1/o3/gpt-oss models)
            reasoning_tokens = StreamingUtils.extract_reasoning_tokens(usage_metadata)
            if reasoning_tokens > 0:
                state.cumulative_usage["reasoning_tokens"] += reasoning_tokens
                log.debug(f"Accumulated {reasoning_tokens} reasoning tokens")

            # Cached tokens
            cached_tokens = usage_dict.get("cache_read_input_tokens", 0) or usage_dict.get(
                "cached_tokens", 0
            )
            if cached_tokens > 0:
                state.cumulative_usage["cached_tokens"] += cached_tokens

        except Exception as e:
            log.error(f"Failed to accumulate usage: {e}")


class SSEEventFormatter:
    """Server-Sent Events (SSE) formatter - returns dicts for sse-starlette."""

    @staticmethod
    def token_event(content: str) -> Dict[str, Any]:
        """Return dict - sse-starlette handles formatting."""
        return {"event": "token", "data": content}

    @staticmethod
    def reasoning_token_event(content: str) -> Dict[str, Any]:
        """Return dict - sse-starlette handles formatting."""
        return {"event": "reasoning", "data": content}

    @staticmethod
    def thinking_event(content: str) -> Dict[str, Any]:
        """Backward compatible alias for reasoning stream event."""
        return {"event": "reasoning", "data": content}

    @staticmethod
    def tool_start_event(tool_name: str, tool_input: Any) -> Dict[str, Any]:
        """Return dict - sse-starlette handles formatting."""
        return {"event": "tool_start", "data": json.dumps({"tool": tool_name, "input": tool_input})}

    @staticmethod
    def tool_end_event(
        tool_name: str, output: str, tool_call_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return dict - sse-starlette handles formatting."""
        return {
            "event": "tool_end",
            "data": json.dumps({"tool": tool_name, "output": output, "tool_call_id": tool_call_id}),
        }

    @staticmethod
    def tool_call_event(
        tool_name: str, output: str, tool_call_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Public-facing tool execution event."""
        return {
            "event": "tool_call",
            "data": json.dumps({"name": tool_name, "output": output, "tool_call_id": tool_call_id}),
        }

    @staticmethod
    def router_event(router_output: Dict[str, Any]) -> Dict[str, Any]:
        """Return dict - sse-starlette handles formatting."""
        return {"event": "router", "data": json.dumps(router_output)}

    @staticmethod
    def cost_event(
        total_cost: float, usage: Dict[str, int], model: str, provider: str, cached: bool = False
    ) -> Dict[str, Any]:
        """Format cost event with reasoning tokens if present."""
        # Clean up zero/None values
        clean_usage = {k: v for k, v in usage.items() if v and v > 0}

        cost_data = {
            "total_cost": round(total_cost, 6),
            "usage": clean_usage,
            "model": model,
            "provider": provider,
            "currency": "USD",
        }
        if cached:
            cost_data["cached"] = True

        return {"event": "cost", "data": json.dumps(cost_data)}

    @staticmethod
    def done_event() -> Dict[str, Any]:
        """Return dict - sse-starlette handles formatting."""
        return {"event": "done", "data": json.dumps({"status": "complete"})}

    @staticmethod
    def trace_event(trace_id: str) -> Dict[str, Any]:
        """Yield the generated trace_id for frontend reference."""
        return {"event": "trace", "data": json.dumps({"trace_id": trace_id})}

    @staticmethod
    def follow_ups_event(questions: list[str]) -> Dict[str, Any]:
        """Emit context-aware follow-up suggestions parsed from the LLM response."""
        return {"event": "follow_ups", "data": json.dumps({"questions": questions})}

    @staticmethod
    def error_event(error_message: str) -> Dict[str, Any]:
        """Return dict - sse-starlette handles formatting."""
        return {"event": "error", "data": json.dumps({"message": error_message})}


# Singleton instances
streaming_utils = StreamingUtils()
sse_formatter = SSEEventFormatter()
