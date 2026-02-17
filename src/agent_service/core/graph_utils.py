"""
LangGraph-specific Utilities
Handles state management, message history, and graph reducers.
"""

import logging
from typing import Any, Dict, List

from langchain_core.messages import BaseMessage, RemoveMessage

from src.agent_service.core.config import KEEP_LAST

log = logging.getLogger(__name__)


class GraphUtils:
    """Utilities for LangGraph state management and message handling."""

    @staticmethod
    def keep_only_last_n_messages(
        state: Dict[str, Any], config: Dict[str, Any], n: int = KEEP_LAST
    ) -> Dict[str, Any]:
        """LangGraph reducer to keep message history short."""
        msgs: List[BaseMessage] = list(state.get("messages", []))

        if len(msgs) <= n:
            return {}

        messages_to_remove = [RemoveMessage(id=msgs[i].id) for i in range(len(msgs) - n) if msgs[i].id is not None]  # type: ignore
        log.debug(f"Trimming {len(messages_to_remove)} messages (keeping last {n})")
        return {"messages": messages_to_remove}


# Singleton instance
graph_utils = GraphUtils()


# Backward compatibility function
def keep_only_last_n_messages(state: dict, config: dict) -> Dict[str, Any]:
    """DEPRECATED: Use graph_utils.keep_only_last_n_messages() instead."""
    return graph_utils.keep_only_last_n_messages(state, config)
