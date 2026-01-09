from langchain_groq import ChatGroq
from agent_config import GROQ_API_KEY, GROQ_BASE_URL, MODEL_NAME

# Initialize LLM
llm = ChatGroq(
    api_key=GROQ_API_KEY, # type: ignore
    base_url=GROQ_BASE_URL,
    model=MODEL_NAME,
    streaming=True,
    temperature=0.0,
    reasoning_format="parsed" # Uncomment if supported by the specific model version
)
