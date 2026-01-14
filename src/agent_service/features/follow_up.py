import logging
import json
import re
import html
from typing import List, Optional, Any, AsyncGenerator, Tuple

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import BaseMessage, HumanMessage, AIMessageChunk
from langchain_core.tools import StructuredTool
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnableParallel
from langchain_core.runnables.passthrough import RunnablePassthrough
from langchain_openai import OpenAIEmbeddings

from src.agent_service.core.schemas import FollowUpResponse, JudgeResponse
from src.agent_service.tools.graph_rag import _GraphVectorSingleton
from src.agent_service.core.config import OPENROUTER_BASE_URL
from src.common.neo4j_mgr import Neo4jManager

log = logging.getLogger("follow_up_gen")

# --- 1. PROMPTS ---

GENERATOR_SYSTEM_PROMPT = """
You are a creative assistant for Mock FinTech.
Your ONLY task is to generate **5 potential follow-up questions** for the USER.

### Context
- The user just received the message below from the Assistant.
- What would the user realistically ask NEXT?

### Related Topics
{related_faqs}

### Available Tools (Reference Only - DO NOT CALL THEM)
{tool_descriptions}

### Guidelines
- **Variety**: Mix specific inquiries (e.g., "What is the interest rate?") with actions (e.g., "Pay my EMI").
- **Perspective**: Use "I", "Me", "My" (User persona).
- **Language**: Use the same language/script as the USER.
- **Punctuation**: Every item MUST end with a question mark `?`.
- **Format**: Return a JSON object: {{"questions": ["Q1?", "Q2?", ...]}}
- **Strict Rule**: Do NOT attempt to answer the user or call tools. JUST generate the questions.
- **Strict Rule**: DO NOT output HTML tags (no <span> etc). ONLY return JSON.
"""

EXPLAIN_WHY_SYSTEM_PROMPT = """
You write a SHORT, user-facing reason for why a suggested follow-up question is relevant.

Rules:
- SAME language/script as the USER.
- Exactly 1 sentence, max 12 words.
- No HTML, no markdown, no quotes.
- Do NOT reveal chain-of-thought. Just a short explanation.
"""

JUDGE_SYSTEM_PROMPT = """
You are a strict Quality Control Judge.
Evaluate the candidate questions based on: Groundedness, Relevance, and Correctness.

### Metrics:
1. **Groundedness**: Does a Tool exist for the action? (If asking for non-existent feature like "Reset Password", Score=1).
2. **Relevance**: Does it follow the conversation flow logically?
3. **Correctness**: Is it safe and non-repetitive?

### Context
History: {recent_history}
Tools: {tool_descriptions}
Candidates: {candidates}

### Output
Return a JSON object with evaluations. Include a "reasoning" field for each score.
Example:
{
  "evaluations": [
    { "question": "...", "reasoning": "...", "groundedness": 1, "relevance": 9, "correctness": 10 }
  ]
}
"""

# --- 2. HTML SANITIZERS (strip theme spans from main agent output) ---

_SPAN_TAG_RE = re.compile(r"</?span\b[^>]*>", re.IGNORECASE)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_ANY_TAG_RE = re.compile(r"<[^>]+>")

def strip_theme_html(s: str) -> str:
    """Remove only <span ...> wrappers while keeping Markdown."""
    if not s:
        return ""
    s = html.unescape(s)
    s = _BR_RE.sub("\n", s)
    s = _SPAN_TAG_RE.sub("", s)
    s = s.replace("\u200b", "")
    return s.strip()

def strip_all_html_tags(s: str) -> str:
    """Emergency fallback: remove ALL HTML tags."""
    if not s:
        return ""
    s = html.unescape(s)
    s = _BR_RE.sub("\n", s)
    s = _ANY_TAG_RE.sub("", s)
    s = s.replace("\u200b", "")
    return s.strip()

def _sanitize_sse_text(s: str) -> str:
    # Avoid multiline SSE data blocks / weird CRs, but PRESERVE spaces.
    return (s or "").replace("\r", "").replace("\n", " ")

# --- 3. Provider-exposed reasoning extraction (best-effort) ---

def _as_dict(x: Any) -> Optional[dict]:
    if isinstance(x, dict):
        return x
    try:
        return dict(x)  # type: ignore
    except Exception:
        return None

def _extract_reasoning_from_openrouter_reasoning_details(raw: Any) -> List[str]:
    """
    OpenRouter reasoning: streaming chunks can expose reasoning_details in delta.
    Some wrappers surface it via additional_kwargs/response_metadata.
    """
    out: List[str] = []
    if not isinstance(raw, AIMessageChunk):
        return out

    rd = (
        raw.additional_kwargs.get("reasoning_details")
        or raw.response_metadata.get("reasoning_details")  # type: ignore
    )
    if not isinstance(rd, list):
        return out

    for item in rd:
        d = item if isinstance(item, dict) else _as_dict(item)
        if not d:
            continue
        t = str(d.get("type") or "")
        if t == "reasoning.text" and d.get("text"):
            out.append(str(d["text"]))
        elif t == "reasoning.summary" and d.get("summary"):
            out.append(str(d["summary"]))
        # ignore reasoning.encrypted
    return out

def _extract_reasoning_from_content_blocks(raw: Any) -> List[str]:
    out: List[str] = []
    blocks = getattr(raw, "content_blocks", None)
    if not blocks:
        return out
    for b in blocks:
        bd = b if isinstance(b, dict) else _as_dict(b)
        if not bd:
            continue
        btype = str(bd.get("type") or "").lower()
        if btype in ("reasoning", "thinking"):
            txt = bd.get("reasoning") or bd.get("text") or bd.get("thinking")
            if txt:
                out.append(str(txt))
    return out

def extract_reasoning_text(raw: Any) -> List[str]:
    out: List[str] = []
    out.extend(_extract_reasoning_from_openrouter_reasoning_details(raw))
    out.extend(_extract_reasoning_from_content_blocks(raw))

    if isinstance(raw, AIMessageChunk):
        for key in ("reasoning_content", "reasoning"):
            v = raw.additional_kwargs.get(key)
            if isinstance(v, str) and v.strip():
                out.append(v)

        try:
            v2 = raw.response_metadata.get("reasoning")  # type: ignore
            if isinstance(v2, str) and v2.strip():
                out.append(v2)
        except Exception:
            pass

    # de-dupe adjacent repeats
    deduped: List[str] = []
    for s in out:
        if not deduped or deduped[-1] != s:
            deduped.append(s)
    return deduped


class FollowUpQuestionGenerator:
    def __init__(self):
        self.json_parser = JsonOutputParser(pydantic_object=FollowUpResponse)
        self.judge_parser = JsonOutputParser(pydantic_object=JudgeResponse)

    def _get_embeddings_model(self, api_key: str):
        return OpenAIEmbeddings(
            model="openai/text-embedding-3-small",
            api_key=api_key, # pyright: ignore[reportArgumentType]
            base_url=OPENROUTER_BASE_URL,
            check_embedding_ctx_length=False,
        )

    def _parse_json_from_text(self, text: str) -> Optional[dict]:
        try:
            if not text:
                return None
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<\|.*?\|>", "", text, flags=re.DOTALL)
            text = strip_all_html_tags(text)

            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
            if match:
                json_str = match.group(1)
            else:
                start = text.find("{")
                end = text.rfind("}")
                if start == -1 or end == -1:
                    return None
                json_str = text[start : end + 1]
            return json.loads(json_str)
        except Exception as e:
            log.warning(f"JSON extraction failed: {e}")
            return None

    async def _stream_with_parallel_parse(
        self,
        chain_input: dict,
        llm: BaseChatModel,
        base_prompt_text: str,
        parser: JsonOutputParser,
    ) -> AsyncGenerator[Any, None]:
        """
        Streams raw + parsed simultaneously.
        - raw: AIMessageChunk (for provider-exposed reasoning)
        - parsed: JsonOutputParser partial dicts
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", base_prompt_text + "\n\n{format_instructions}"),
                (
                    "human",
                    "Conversation context:\n"
                    "User: {last_user}\n"
                    "Assistant: {last_ai}\n\n"
                    "Return ONLY valid JSON (no markdown fences, no HTML, no extra text).",
                ),
            ]
        )

        chain_input["format_instructions"] = parser.get_format_instructions()

        # No tools
        try:
            llm = llm.bind(tool_choice="none") # pyright: ignore[reportAssignmentType]
        except Exception:
            pass

        # If supported: JSON mode
        try:
            llm = llm.bind(response_format={"type": "json_object"}) # pyright: ignore[reportAssignmentType]
        except Exception:
            pass

        chain = (
            prompt
            | llm
            | RunnableParallel(
                raw=RunnablePassthrough(),
                text=StrOutputParser(),
                parsed=(StrOutputParser() | parser),
            )
        )

        last_parsed: Optional[Any] = None
        full_text: List[str] = []

        async for chunk in chain.astream(chain_input):
            raw_msg = chunk.get("raw")
            txt = chunk.get("text")
            parsed = chunk.get("parsed")

            if isinstance(txt, str) and txt:
                full_text.append(txt)

            for r in extract_reasoning_text(raw_msg):
                rr = _sanitize_sse_text(r)
                if rr:
                    yield {"event": "reasoning_token", "data": rr}

            if parsed is not None:
                last_parsed = parsed
                yield {"event": "parsed_partial", "data": parsed}

        final_obj: Optional[dict] = None
        if isinstance(last_parsed, dict):
            final_obj = last_parsed
        elif last_parsed is not None:
            try:
                final_obj = last_parsed.model_dump()  # type: ignore
            except Exception:
                try:
                    final_obj = dict(last_parsed)  # type: ignore
                except Exception:
                    final_obj = None

        if final_obj is None:
            parsed_fallback = self._parse_json_from_text("".join(full_text))
            if parsed_fallback is not None:
                final_obj = parsed_fallback

        if final_obj is not None:
            yield {"event": "final", "data": final_obj}
        else:
            yield {"event": "error", "data": "Failed to parse JSON"}

    async def _stream_why_for_candidate(
        self,
        llm: BaseChatModel,
        last_user: str,
        last_ai: str,
        question: str,
        candidate_id: int,
    ) -> AsyncGenerator[dict, None]:
        """
        Streams a short, user-facing "why" token-by-token for one candidate.
        This is NOT chain-of-thought; it's a brief explanation.
        """
        try:
            llm2 = llm.bind(tool_choice="none")
        except Exception:
            llm2 = llm

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", EXPLAIN_WHY_SYSTEM_PROMPT),
                (
                    "human",
                    "Context:\n"
                    "User: {last_user}\n"
                    "Assistant: {last_ai}\n\n"
                    "Suggested follow-up question: {question}\n\n"
                    "Write the short reason now.",
                ),
            ]
        )

        chain = prompt | llm2
        buf = ""

        async for chunk in chain.astream(
            {"last_user": last_user, "last_ai": last_ai, "question": question}
        ):
            tok = getattr(chunk, "content", None)
            if not tok:
                continue

            # Use the updated sanitizer (or raw replace) to keep spaces
            t = str(tok).replace("\r", "").replace("\n", " ")
            
            # If the token was just a newline that became a space, or an empty token, handle accordingly
            if not t:
                continue

            buf += t
            yield {
                "event": "candidate_why_token",
                "data": json.dumps({"id": candidate_id, "token": t}, ensure_ascii=False),
            }

        # Final cleanup is safe here because it's the whole string
        why = strip_all_html_tags(buf).strip()
        if why:
            yield {
                "event": "candidate_why_done",
                "data": json.dumps({"id": candidate_id, "why": why}, ensure_ascii=False),
            }

    async def _generate_with_fallback_invoke(
        self,
        chain_input: dict,
        llm: BaseChatModel,
        base_prompt_text: str,
        parser: JsonOutputParser,
    ) -> Any:
        prompt = ChatPromptTemplate.from_messages([("system", base_prompt_text), ("placeholder", "{messages}")])
        try:
            struct_llm = llm.with_structured_output(parser.pydantic_object)
            return await (prompt | struct_llm).ainvoke(chain_input)
        except Exception:
            fallback_prompt = ChatPromptTemplate.from_messages(
                [("system", base_prompt_text + "\n{format_instructions}"), ("placeholder", "{messages}")]
            )
            chain_input["format_instructions"] = parser.get_format_instructions()
            try:
                llm = llm.bind(tool_choice="none") # type: ignore
            except Exception:
                pass
            raw = await (fallback_prompt | llm | StrOutputParser()).ainvoke(chain_input)
            return self._parse_json_from_text(raw)

    # --- PUBLIC API ---

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

        last_user_msg = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        last_ai_msg = next((m for m in reversed(messages) if getattr(m, "type", "") == "ai"), None)

        last_user_raw = str(getattr(last_user_msg, "content", "") or "") if last_user_msg else ""
        last_ai_raw = str(getattr(last_ai_msg, "content", "") or "") if last_ai_msg else ""

        last_user = strip_theme_html(last_user_raw)
        last_ai = strip_theme_html(last_ai_raw)

        context_text = f"User: {last_user}\nAI: {last_ai}".strip()

        try:
            # 1) CACHE
            yield {"event": "status", "data": "Checking cache..."}
            if openrouter_key:
                cached = await self._fetch_cached_response(context_text, openrouter_key)
                if cached:
                    yield {"event": "status", "data": "Cache hit! ⚡"}
                    # final only: result
                    yield {"event": "result", "data": json.dumps(cached, ensure_ascii=False)}
                    yield {"event": "done", "data": "[DONE]"}
                    return

            # 2) CONTEXT
            yield {"event": "status", "data": "Reading context..."}
            related_faqs_str = await self._fetch_related_faqs(messages, openrouter_key)
            tool_desc_str = "\n".join([f"- {t.name}: {t.description}" for t in tools])

            # 3) GENERATION (stream candidates + why tokens)
            yield {"event": "status", "data": "Brainstorming ideas..."}

            seen_questions: List[str] = []
            seen_set = set()

            final_payload: Optional[dict] = None

            async for packet in self._stream_with_parallel_parse(
                {
                    "last_user": last_user,
                    "last_ai": last_ai,
                    "tool_descriptions": tool_desc_str,
                    "related_faqs": related_faqs_str,
                },
                llm,
                GENERATOR_SYSTEM_PROMPT,
                self.json_parser,
            ):
                ev = packet.get("event")

                if ev == "reasoning_token":
                    yield {"event": "reasoning", "data": packet.get("data", "")}

                elif ev == "parsed_partial":
                    partial = packet.get("data")
                    if isinstance(partial, dict) and isinstance(partial.get("questions"), list):
                        qs = partial.get("questions") or []
                        for q in qs:
                            if not isinstance(q, str):
                                continue

                            qq = strip_all_html_tags(q).strip()
                            if not qq:
                                continue
                            # emit only completed question strings
                            if not qq.endswith("?"):
                                continue

                            if qq in seen_set:
                                continue

                            seen_set.add(qq)
                            cand_id = len(seen_questions)
                            if cand_id >= 5:
                                continue

                            seen_questions.append(qq)

                            yield {"event": "status", "data": f"Drafting follow-ups ({len(seen_questions)}/5)..."}
                            yield {
                                "event": "candidate",
                                "data": json.dumps({"id": cand_id, "question": qq}, ensure_ascii=False),
                            }

                            # token-by-token WHY for this candidate
                            async for why_ev in self._stream_why_for_candidate(
                                llm=llm,
                                last_user=last_user,
                                last_ai=last_ai,
                                question=qq,
                                candidate_id=cand_id,
                            ):
                                yield why_ev

                elif ev == "final":
                    if isinstance(packet.get("data"), dict):
                        final_payload = packet["data"]

                elif ev == "error":
                    yield {"event": "error", "data": packet.get("data", "Follow-up generation error")}
                    yield {"event": "done", "data": "[DONE]"}
                    return

            # If nothing streamed, fall back to final payload (no candidate streaming in that case)
            candidates: List[str] = seen_questions[:]
            if not candidates and final_payload and isinstance(final_payload.get("questions"), list):
                raw_qs = final_payload.get("questions") or []
                for q in raw_qs:
                    if isinstance(q, str):
                        qq = strip_all_html_tags(q).strip()
                        if qq:
                            candidates.append(qq)
                candidates = candidates[:5]

            if not candidates:
                yield {"event": "error", "data": "No questions generated"}
                yield {"event": "done", "data": "[DONE]"}
                return

            # 4) JUDGING (final selection)
            yield {"event": "status", "data": "Reviewing quality..."}
            final_questions = await self._judge_candidates(candidates, messages, llm, tool_desc_str)

            # 5) CACHE FINAL & EMIT FINAL RESULT
            if final_questions and openrouter_key:
                await self._cache_results(context_text, final_questions, openrouter_key)

            # ✅ Option 2: only final judged list as result
            yield {"event": "result", "data": json.dumps(final_questions, ensure_ascii=False)}
            yield {"event": "done", "data": "[DONE]"}

        except Exception as e:
            log.error(f"Stream error: {e}")
            yield {"event": "error", "data": str(e)}
            yield {"event": "done", "data": "[DONE]"}

    async def generate_questions(
        self,
        messages: List[BaseMessage],
        llm: BaseChatModel,
        tools: List[StructuredTool],
        openrouter_key: Optional[str] = None,
        nvidia_key: Optional[str] = None,
    ) -> List[str]:
        final_questions: List[str] = []
        try:
            async for event in self.generate_questions_stream(
                messages=messages,
                llm=llm,
                tools=tools,
                openrouter_key=openrouter_key,
                nvidia_key=nvidia_key,
            ):
                if event.get("event") == "result":
                    final_questions = json.loads(event["data"])
            return final_questions
        except Exception as e:
            log.error(f"Non-streaming generation failed: {e}")
            return []

    # --- HELPERS ---

    async def _fetch_cached_response(self, context_text: str, openrouter_key: str) -> List[str]:
        if not context_text or not openrouter_key:
            return []
        try:
            emb_model = self._get_embeddings_model(openrouter_key)
            vector = await emb_model.aembed_query(context_text)

            driver = Neo4jManager.get_driver()
            with driver.session() as session:
                session.run(
                    "CREATE VECTOR INDEX followup_context_embeddings IF NOT EXISTS "
                    "FOR (c:FollowUpContext) ON (c.embedding) "
                    "OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}"
                )
                result = session.run(
                    "CALL db.index.vector.queryNodes('followup_context_embeddings', 1, $vector) "
                    "YIELD node, score "
                    "WHERE score >= 0.92 "
                    "MATCH (node)-[:HAS_SUGGESTION]->(q:SuggestedQuestion) "
                    "RETURN q.text as question",
                    vector=vector,
                )
                cached = [r["question"] for r in result]
                if cached:
                    log.info(f"⚡ Cache Hit! {len(cached)} follow-ups.")
                    return cached[:3]
        except Exception:
            pass
        return []

    async def _cache_results(self, context_text: str, questions: List[str], openrouter_key: str):
        if not context_text or not questions or not openrouter_key:
            return
        try:
            emb_model = self._get_embeddings_model(openrouter_key)
            vector = await emb_model.aembed_query(context_text)

            driver = Neo4jManager.get_driver()
            with driver.session() as session:
                session.run(
                    "MERGE (c:FollowUpContext {text: $context}) "
                    "ON CREATE SET c.embedding = $vector "
                    "WITH c "
                    "UNWIND $questions AS q_text "
                    "MERGE (q:SuggestedQuestion {text: q_text}) "
                    "MERGE (c)-[:HAS_SUGGESTION]->(q)",
                    context=context_text,
                    vector=vector,
                    questions=questions,
                )
        except Exception:
            pass

    async def _fetch_related_faqs(self, messages: List[BaseMessage], openrouter_key: Optional[str]) -> str:
        if not openrouter_key:
            return ""
        try:
            last_user = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
            if not last_user:
                return ""
            vector_store = _GraphVectorSingleton.get_vector_store(api_key=openrouter_key)
            results_with_scores = vector_store.similarity_search_with_relevance_scores(
                str(last_user.content), 
                k=3
                )
            threshold = 0.7
            return "\n".join([f"- {doc.page_content}" for doc, score in results_with_scores if score >= threshold])
        except Exception:
            return ""

    async def _judge_candidates(
        self,
        candidates: List[str],
        messages: List[BaseMessage],
        llm: BaseChatModel,
        tool_desc_str: str,
    ) -> List[str]:
        if not candidates:
            return []
        try:
            history_text = ""
            for m in messages[-3:]:
                role = "User" if isinstance(m, HumanMessage) else "Assistant"
                content = str(m.content)[:300] if getattr(m, "content", None) else ""
                history_text += f"{role}: {content}\n"

            evaluation = await self._generate_with_fallback_invoke(
                {
                    "recent_history": history_text,
                    "tool_descriptions": tool_desc_str,
                    "candidates": "\n".join([f"- {c}" for c in candidates]),
                    "messages": [],
                },
                llm,
                JUDGE_SYSTEM_PROMPT,
                self.judge_parser,
            )

            eval_list = []
            if isinstance(evaluation, dict):
                eval_list = evaluation.get("evaluations", [])
            elif evaluation:
                eval_list = getattr(evaluation, "evaluations", [])

            valid_items: List[Tuple[float, str]] = []
            for item in eval_list:
                if isinstance(item, dict):
                    q = item.get("question")
                    s = (
                        item.get("relevance", 0) * 0.5
                        + item.get("groundedness", 0) * 0.3
                        + item.get("correctness", 0) * 0.2
                    )
                else:
                    q = item.question
                    s = item.relevance * 0.5 + item.groundedness * 0.3 + item.correctness * 0.2

                if s >= 7.0 and q:
                    qq = strip_all_html_tags(str(q)).strip()
                    if qq:
                        valid_items.append((float(s), qq))

            valid_items.sort(key=lambda x: x[0], reverse=True)
            if not valid_items:
                return candidates[:3]
            return [q for _, q in valid_items[:3]]

        except Exception as e:
            log.error(f"Judge failed: {e}")
            return candidates[:3]

    async def get_all_cached_questions(self) -> List[dict]:
        try:
            driver = Neo4jManager.get_driver()
            with driver.session() as session:
                result = session.run(
                    "MATCH (c:FollowUpContext)-[:HAS_SUGGESTION]->(q:SuggestedQuestion) "
                    "RETURN c.text as context, collect(q.text) as questions "
                    "ORDER BY c.text LIMIT 100"
                )
                return [{"context": r["context"], "questions": r["questions"]} for r in result]
        except Exception:
            return []


follow_up_service = FollowUpQuestionGenerator()