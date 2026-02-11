from typing import List, Optional
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

def build_byok_agent(
    model: BaseChatModel,
    tools: List[BaseTool],
    checkpointer: Optional[BaseCheckpointSaver] = None,
    system_prompt: str = ""
):
    """
    Builds a LangGraph ReAct agent using pre-instantiated BYOK components.
    No internal key lookups or factory calls allowed.
    """
    return create_react_agent(
        model=model,
        tools=tools,
        checkpointer=checkpointer,
        state_modifier=system_prompt
    )
