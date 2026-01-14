import logging
import json
import re
from typing import List, cast, Optional, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import StructuredTool
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_openai import OpenAIEmbeddings

from src.agent_service.schemas import FollowUpResponse, JudgeResponse
from src.agent_service.graph_tool import _GraphVectorSingleton 
from src.agent_service.config import OPENROUTER_BASE_URL
from src.common.neo4j_mgr import Neo4jManager

log = logging.getLogger("follow_up_gen")

GENERATOR_SYSTEM_PROMPT = """
You are a creative assistant for Hero Fincorp.
Your ONLY task is to generate **5 potential follow-up questions** for the USER.

### Context
- The user just received the message below from the Assistant.
- What would the user realistically ask NEXT?

### Related Topics
{related_faqs}

### Available Tools (For Reference Only - DO NOT CALL THEM)
{tool_descriptions}

### Guidelines
- **Variety**: Mix specific inquiries (e.g., "What is the interest rate?") with actions (e.g., "Pay my EMI").
- **Perspective**: Use "I", "Me", "My" (User persona).
- **Format**: Return a structured JSON object.
- **Strict Rule**: Do NOT attempt to answer the user or call tools. JUST generate the questions.
"""

JUDGE_SYSTEM_PROMPT = """
You are a strict Quality Control Judge.
Evaluate the candidate questions based on the following metrics (1-10):

1. **Groundedness (Critical)**:
   - Does the question imply an action? If yes, **does a Tool exist for it**?
   - If the user asks for a feature (e.g., "Reset Password", "Biometric Login") and that Tool is NOT listed, **Score = 1**.

2. **Relevance**:
   - Does it make sense immediately after the Last AI Response?

3. **Correctness**:
   - Is it safe, grammatically correct, and NOT a repetition?

### Recent Conversation History
{recent_history}

### Available Tools
{tool_descriptions}

### Candidates
{candidates}

Return the evaluations for ALL candidates.
"""

class FollowUpQuestionGenerator:
    def __init__(self):
        self.json_parser = JsonOutputParser(pydantic_object=FollowUpResponse)
        self.judge_parser = JsonOutputParser(pydantic_object=JudgeResponse)

    def _get_embeddings_model(self, api_key: str):
        return OpenAIEmbeddings(
            model="openai/text-embedding-3-small",
            api_key=api_key, # type: ignore
            base_url=OPENROUTER_BASE_URL,
            check_embedding_ctx_length=False,
        )

    async def _fetch_cached_response(self, context_text: str, openrouter_key: str) -> List[str]:
        if not context_text or not openrouter_key: return []
        try:
            emb_model = self._get_embeddings_model(openrouter_key)
            vector = await emb_model.aembed_query(context_text)
            
            driver = Neo4jManager.get_driver()
            with driver.session() as session:
                session.run("""
                    CREATE VECTOR INDEX followup_context_embeddings IF NOT EXISTS
                    FOR (c:FollowUpContext) ON (c.embedding)
                    OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
                """)
                result = session.run("""
                    CALL db.index.vector.queryNodes('followup_context_embeddings', 1, $vector)
                    YIELD node, score
                    WHERE score >= 0.92
                    MATCH (node)-[:HAS_SUGGESTION]->(q:SuggestedQuestion)
                    RETURN q.text as question
                """, vector=vector)
                cached_questions = [r["question"] for r in result]
                if cached_questions:
                    log.info(f"⚡ Cache Hit! Found {len(cached_questions)} follow-ups.")
                    return cached_questions[:3]
        except Exception as e:
            log.warning(f"Cache fetch warning: {e}")
        return []

    async def _cache_results(self, context_text: str, questions: List[str], openrouter_key: str):
        if not context_text or not questions or not openrouter_key: return
        try:
            emb_model = self._get_embeddings_model(openrouter_key)
            vector = await emb_model.aembed_query(context_text)
            driver = Neo4jManager.get_driver()
            with driver.session() as session:
                session.run("""
                    MERGE (c:FollowUpContext {text: $context})
                    ON CREATE SET c.embedding = $vector
                    WITH c
                    UNWIND $questions AS q_text
                    MERGE (q:SuggestedQuestion {text: q_text})
                    MERGE (c)-[:HAS_SUGGESTION]->(q)
                """, context=context_text, vector=vector, questions=questions)
        except Exception as e:
            log.warning(f"Cache write warning: {e}")

    async def _fetch_related_faqs(self, messages: List[BaseMessage], openrouter_key: Optional[str]) -> str:
        if not openrouter_key: return ""
        try:
            last_user = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
            query = last_user.content if last_user else ""
            if not query: return ""
            vector_store = _GraphVectorSingleton.get_vector_store(api_key=openrouter_key)
            results = vector_store.similarity_search(str(query), k=3)
            return "\n".join([f"- {doc.page_content}" for doc in results])
        except Exception as e:
            log.warning(f"Context retrieval failed: {e}")
            return ""

    def _parse_json_from_text(self, text: str) -> Optional[dict]:
        try:
            # 1. Strip special tokens and thinking blocks
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            text = re.sub(r'<\|.*?\|>', '', text, flags=re.DOTALL) # Remove tool tokens
            
            # 2. Extract from Markdown code blocks
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1:
                    json_str = text[start : end + 1]
                else:
                    return None

            return json.loads(json_str)
        except Exception as e:
            log.warning(f"JSON extraction failed: {e}")
            return None

    async def _generate_with_fallback(self, chain_input: dict, llm: BaseChatModel, base_prompt_text: str, parser: JsonOutputParser) -> Any:
        prompt = ChatPromptTemplate.from_messages([
            ("system", base_prompt_text),
            ("placeholder", "{messages}")
        ])

        # 1. SKIP Structured Output for known incompatible models
        model_name = getattr(llm, "model_name", "").lower()
        skip_structured = any(x in model_name for x in ["moonshot", "thinking", "r1"])

        if not skip_structured:
            try:
                # Force tool_choice='none' if supported to prevent the tool call error
                # Note: Not all providers support this via bind_tools, so we rely on prompt for fallback
                struct_llm = llm.with_structured_output(parser.pydantic_object)
                chain = prompt | struct_llm
                res = await chain.ainvoke(chain_input)
                if res: return res
            except Exception as e:
                log.debug(f"Structured output failed ({e}), attempting fallback...")

        # 2. Manual Fallback: Raw String -> Regex Extraction
        try:
            fallback_prompt = ChatPromptTemplate.from_messages([
                ("system", base_prompt_text + "\n\nRESPONSE FORMAT:\n{format_instructions}\n\nEnsure valid JSON. DO NOT call tools."),
                ("placeholder", "{messages}")
            ])
            
            # Use StrOutputParser to get raw text
            chain = fallback_prompt | llm | StrOutputParser()
            chain_input["format_instructions"] = parser.get_format_instructions()
            
            # Explicitly disable tools in the call if the API supports it
            # This is provider-dependent, but often 'tool_choice'='none' works in bind
            try:
                 llm_no_tools = llm.bind(tool_choice="none")
                 chain = fallback_prompt | llm_no_tools | StrOutputParser()
            except:
                 pass # If bind fails, just use base llm
            
            raw_output = await chain.ainvoke(chain_input)
            return self._parse_json_from_text(raw_output)

        except Exception as e:
            log.error(f"Fallback generation failed: {e}")
            return None

    async def _judge_candidates(self, candidates: List[str], messages: List[BaseMessage], llm: BaseChatModel, tool_desc_str: str) -> List[str]:
        if not candidates: return []
        try:
            history_text = ""
            for m in messages[-3:]:
                role = "User" if isinstance(m, HumanMessage) else "Assistant"
                content = str(m.content)[:300] if m.content else ""
                history_text += f"{role}: {content}\n"

            evaluation = await self._generate_with_fallback(
                {
                    "recent_history": history_text,  
                    "tool_descriptions": tool_desc_str,
                    "candidates": "\n".join([f"- {c}" for c in candidates]),
                    "messages": [] 
                },
                llm, 
                JUDGE_SYSTEM_PROMPT, 
                self.judge_parser
            )

            eval_list = []
            if isinstance(evaluation, dict):
                eval_list = evaluation.get("evaluations", [])
            elif evaluation:
                eval_list = getattr(evaluation, "evaluations", [])

            valid_items = []
            for item in eval_list:
                if isinstance(item, dict):
                    q, g, r, c = item.get("question"), item.get("groundedness", 0), item.get("relevance", 0), item.get("correctness", 0)
                else:
                    q, g, r, c = item.question, item.groundedness, item.relevance, item.correctness

                score = (r * 0.5) + (g * 0.3) + (c * 0.2)
                log.info(f"📊 '{q}' | Score: {score:.2f} (G:{g} R:{r} C:{c})")

                if q and "<span" in q: continue

                if score >= 7.0:
                    valid_items.append((score, q))

            valid_items.sort(key=lambda x: x[0], reverse=True)
            if not valid_items: return candidates[:3] 
            return [q for _, q in valid_items[:3]]

        except Exception as e:
            log.error(f"Judge failed: {e}")
            return candidates[:3]

    async def generate_questions(
        self, 
        messages: List[BaseMessage], 
        llm: BaseChatModel, 
        tools: List[StructuredTool],
        openrouter_key: Optional[str] = None, 
        nvidia_key: Optional[str] = None
    ) -> List[str]:
        if not messages: return []

        last_ai = messages[-1].content if messages else ""
        last_user = messages[-2].content if len(messages) > 1 else ""
        context_text = f"User: {last_user}\nAI: {last_ai}".strip()

        try:
            if openrouter_key:
                cached = await self._fetch_cached_response(context_text, openrouter_key)
                if cached: return cached

            related_faqs_str = await self._fetch_related_faqs(messages, openrouter_key)
            tool_desc_str = "\n".join([f"- {t.name}: {t.description}" for t in tools])
            
            gen_response = await self._generate_with_fallback(
                {
                    "messages": messages[-6:],
                    "tool_descriptions": tool_desc_str,
                    "related_faqs": related_faqs_str
                },
                llm, 
                GENERATOR_SYSTEM_PROMPT, 
                self.json_parser
            )
            
            candidates = []
            if isinstance(gen_response, dict):
                candidates = gen_response.get("questions", [])
            elif gen_response:
                candidates = getattr(gen_response, "questions", [])

            if not candidates:
                log.warning("Generator returned no questions.")
                return []

            final_questions = await self._judge_candidates(candidates, messages, llm, tool_desc_str)

            if final_questions and openrouter_key:
                await self._cache_results(context_text, final_questions, openrouter_key)

            return final_questions

        except Exception as e:
            log.error(f"Failed to generate follow-up questions: {e}")
            return []
        
    async def get_all_cached_questions(self) -> List[dict]:
        """
        Retrieves all cached follow-up contexts and their associated questions.
        Useful for debugging or admin dashboards.
        """
        try:
            driver = Neo4jManager.get_driver()
            # Note: Using sync session here is fine for admin endpoints
            with driver.session() as session:
                result = session.run("""
                    MATCH (c:FollowUpContext)-[:HAS_SUGGESTION]->(q:SuggestedQuestion)
                    RETURN c.text as context, collect(q.text) as questions
                    ORDER BY c.text
                    LIMIT 100
                """)
                
                data = []
                for record in result:
                    data.append({
                        "context": record["context"],
                        "questions": record["questions"]
                    })
                return data

        except Exception as e:
            log.error(f"Failed to fetch cached followups: {e}")
            return []

follow_up_service = FollowUpQuestionGenerator()