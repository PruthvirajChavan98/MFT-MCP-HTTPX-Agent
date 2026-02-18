import asyncio
import json
import logging
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import StructuredTool

# Enterprise Imports
from src.agent_service.llm.client import get_embeddings
from src.common.neo4j_mgr import Neo4jManager

log = logging.getLogger("follow_up_gen")


# --- 1. Strategies (The "Angles") ---
class FollowUpAngle(str, Enum):
    DIRECT_NEXT_STEP = "Direct Next Step"
    MISSING_INFO = "Clarification / Missing Info"
    ALTERNATIVE_OPTION = "Alternative Path"
    HUMAN_SUPPORT = "Human Support / Escalation"
    RELATED_TOPIC = "Related Feature"


ANGLE_PROMPTS = {
    FollowUpAngle.DIRECT_NEXT_STEP: "Ask for the immediate logical next step based on the assistant's answer.",
    FollowUpAngle.MISSING_INFO: "Ask for specific details or clarification that wasn't fully explained.",
    FollowUpAngle.ALTERNATIVE_OPTION: "Ask about a different way to achieve the goal or a different product option.",
    FollowUpAngle.HUMAN_SUPPORT: "Ask how to contact support, raise a ticket, or speak to a human.",
    FollowUpAngle.RELATED_TOPIC: "Ask about a related feature or policy mentioned in the context (e.g., fees, timelines).",
}

BASE_SYSTEM_PROMPT = """
You are a helpful user assistant.
Your task is to generate EXACTLY ONE short follow-up question (max 10 words) from the USER'S perspective ("I", "Me").
Do not output anything else. No bullets, no numbering, no JSON. Just the text.
"""

# --- 2. Service Class ---


class FollowUpQuestionGenerator:
    def __init__(self):
        pass

    async def generate_questions(
        self,
        messages: List[BaseMessage],
        llm: BaseChatModel,
        tools: List[StructuredTool],
        openrouter_key: Optional[str] = None,
        nvidia_key: Optional[str] = None,
    ) -> List[str]:
        """
        Non-streaming wrapper. Consumes the stream internally and returns the final list.
        Used by the /agent/follow-up endpoint.
        """
        collected_questions: Dict[int, str] = {}

        async for event in self.generate_questions_stream(
            messages=messages,
            llm=llm,
            tools=tools,
            openrouter_key=openrouter_key,
            nvidia_key=nvidia_key,
        ):
            if event["event"] == "token":
                data = json.loads(event["data"])
                idx = data["index"]
                token = data["token"]
                collected_questions[idx] = collected_questions.get(idx, "") + token

        # Sort by index to maintain order and return list
        return [
            collected_questions[i].strip()
            for i in sorted(collected_questions.keys())
            if collected_questions[i].strip()
        ]

    async def generate_questions_stream(
        self,
        messages: List[BaseMessage],
        llm: BaseChatModel,
        tools: List[StructuredTool],
        openrouter_key: Optional[str] = None,
        nvidia_key: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:

        if not messages:
            yield {"event": "done", "data": "[DONE]"}
            return

        # 1. Prepare Context (Lite)
        last_user = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
        last_ai = next((m.content for m in reversed(messages) if isinstance(m, AIMessage)), "")

        context_str = f"User: {last_user}\nAssistant: {last_ai}"

        # 2. Check Cache First (RAG)
        if openrouter_key:
            yield {"event": "status", "data": "Checking cache..."}
            cached = await self._fetch_cached_response(context_str, openrouter_key)
            if cached:
                yield {"event": "status", "data": "Cache hit! ⚡"}
                for i, q in enumerate(cached):
                    yield {
                        "event": "token",
                        "data": json.dumps({"index": i, "token": q}, ensure_ascii=False),
                    }
                yield {"event": "done", "data": "[DONE]"}
                return

        yield {"event": "status", "data": "Initializing parallel streams..."}

        # 3. Setup Parallel Tasks
        queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()

        angles = [
            FollowUpAngle.DIRECT_NEXT_STEP,
            FollowUpAngle.MISSING_INFO,
            FollowUpAngle.ALTERNATIVE_OPTION,
            FollowUpAngle.HUMAN_SUPPORT,
            FollowUpAngle.RELATED_TOPIC,
        ]

        tasks = []
        for idx, angle in enumerate(angles):
            tasks.append(
                asyncio.create_task(
                    self._stream_single_question(
                        index=idx, angle=angle, context=context_str, llm=llm, queue=queue
                    )
                )
            )

        # 4. Stream Multiplexer
        active_tasks = len(tasks)
        collected_questions: Dict[int, str] = {}

        try:
            while active_tasks > 0:
                item = await queue.get()

                if item is None:
                    active_tasks -= 1
                    queue.task_done()
                    continue

                if "token" in item:
                    idx = item["index"]
                    tok = item["token"]
                    collected_questions[idx] = collected_questions.get(idx, "") + tok

                    yield {"event": "token", "data": json.dumps(item, ensure_ascii=False)}

                queue.task_done()

        except asyncio.CancelledError:
            log.warning("Follow-up stream cancelled.")
            for t in tasks:
                t.cancel()
            raise

        # 5. Background Cache Write
        if openrouter_key and collected_questions:
            final_qs = [
                collected_questions[i].strip()
                for i in sorted(collected_questions.keys())
                if collected_questions[i].strip()
            ]
            if final_qs:
                asyncio.create_task(self._cache_results(context_str, final_qs, openrouter_key))

        yield {"event": "done", "data": "[DONE]"}

    async def _stream_single_question(
        self,
        index: int,
        angle: FollowUpAngle,
        context: str,
        llm: BaseChatModel,
        queue: asyncio.Queue,
    ):
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", BASE_SYSTEM_PROMPT),
                ("human", f"Context:\n{context}\n\nTask: {ANGLE_PROMPTS[angle]}\n\nQuestion:"),
            ]
        )

        chain = prompt | llm | StrOutputParser()

        try:
            async for chunk in chain.astream({}):
                if chunk:
                    token = chunk.replace("\n", " ")
                    await queue.put({"index": index, "token": token})
        except Exception as e:
            log.error(f"Task {index} ({angle}) failed: {e}")
        finally:
            await queue.put(None)

    # --- Caching & Admin Methods ---

    async def _fetch_cached_response(self, context_text: str, api_key: str) -> List[str]:
        """RAG Retrieval for similar past conversations."""
        try:
            embeddings = get_embeddings(api_key=api_key)
            vector = await embeddings.aembed_query(context_text)

            Neo4jManager.execute_write(
                "CREATE VECTOR INDEX followup_context_embeddings IF NOT EXISTS "
                "FOR (c:FollowUpContext) ON (c.embedding) "
                "OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}"
            )

            result = Neo4jManager.execute_read(
                "CALL db.index.vector.queryNodes('followup_context_embeddings', 1, $vector) "
                "YIELD node, score "
                "WHERE score >= 0.95 "
                "MATCH (node)-[:HAS_SUGGESTION]->(q:SuggestedQuestion) "
                "RETURN q.text as question",
                {"vector": vector},
            )

            return [r["question"] for r in result][:5]
        except Exception as e:
            log.warning(f"Cache fetch failed: {e}")
            return []

    async def _cache_results(self, context_text: str, questions: List[str], api_key: str):
        """Write successful generations to Neo4j."""
        try:
            embeddings = get_embeddings(api_key=api_key)
            vector = await embeddings.aembed_query(context_text)

            Neo4jManager.execute_write(
                """
                MERGE (c:FollowUpContext {text: $context})
                ON CREATE SET c.embedding = $vector, c.created_at = datetime()
                WITH c
                UNWIND $questions AS q_text
                MERGE (q:SuggestedQuestion {text: q_text})
                MERGE (c)-[:HAS_SUGGESTION]->(q)
                """,
                {"context": context_text, "vector": vector, "questions": questions},
            )
        except Exception as e:
            log.warning(f"Cache write failed: {e}")

    async def get_all_cached_questions(self) -> List[dict]:
        """Admin method to fetch all cached follow-up pairs."""
        try:
            result = Neo4jManager.execute_read(
                "MATCH (c:FollowUpContext)-[:HAS_SUGGESTION]->(q:SuggestedQuestion) "
                "RETURN c.text as context, collect(q.text) as questions "
                "ORDER BY c.created_at DESC LIMIT 100"
            )
            return [{"context": r["context"], "questions": r["questions"]} for r in result]
        except Exception as e:
            log.error(f"Admin fetch failed: {e}")
            return []


follow_up_service = FollowUpQuestionGenerator()
