from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agent_service.core.config import JUDGE_MODEL_NAME
from src.agent_service.core.prompts import prompt_manager
from src.agent_service.llm.client import get_llm

log = logging.getLogger("eval_judge")

# --- Schemas ---


class PointwiseScore(BaseModel):
    score: int = Field(description="The integer score (1-5) based on the criteria.")
    reasoning: str = Field(description="Chain-of-thought reasoning justifying the score.")


class PairwiseVerdict(BaseModel):
    winner: Literal["A", "B", "Tie"] = Field(description="Which response is better?")
    reasoning: str = Field(description="Comparison logic explaining the verdict.")


# --- Criteria Definitions ---

METRICS = {
    "correctness": {
        "desc": "Determine if the answer is factually correct based on the provided Context/Evidence. If no context is provided, rely on general world knowledge but prioritize the context.",
        "steps": "1. Identify claims in the response.\\n2. Verify each claim against the Context.\\n3. Penalize hallucinations or contradictions.\\n4. Score 5 for fully supported, 1 for complete fabrication.",
    },
    "relevance": {
        "desc": "Determine if the answer directly addresses the User Input without unnecessary fluff or deflection.",
        "steps": "1. Identify the core intent of the user query.\\n2. Check if the response answers that intent.\\n3. Penalize redundant info or refusal to answer.\\n4. Score 5 for direct/concise answers, 1 for irrelevant responses.",
    },
    "faithfulness": {
        "desc": "Evaluate if the response is derived *solely* from the provided Context. This measures hallucination relative to the RAG context.",
        "steps": "1. Extract all claims in the response.\\n2. Check if each claim exists in the Retrieval Context.\\n3. Any claim NOT in context = Hallucination (even if true in real life).\\n4. Score 5 if 100% grounded, 1 if <20% grounded.",
    },
    "helpfulness": {
        "desc": "Assess how useful, clear, and empathetic the response is to the user.",
        "steps": "1. Check for clarity and structure (markdown, lists).\\n2. Check for tone (professional yet approachable).\\n3. Did it solve the user's problem?\\n4. Score 5 for perfect assistance, 1 for unhelpful/rude.",
    },
    "coherence": {
        "desc": "Evaluate the logical flow, structure, and clarity of the response.",
        "steps": "1. Check if the response is well-structured and easy to read.\\n2. Ensure ideas flow logically from one to the next.\\n3. Check for grammatical correctness and professional tone.\\n4. Score 5 for perfectly coherent, 1 for disjointed/confusing.",
    },
}


class LLMJudge:
    def __init__(
        self,
        model_name: str = JUDGE_MODEL_NAME,
        openrouter_api_key: Optional[str] = None,
        nvidia_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
    ):
        self.model_name = model_name
        self.openrouter_api_key = openrouter_api_key
        self.nvidia_api_key = nvidia_api_key
        self.groq_api_key = groq_api_key
        self.pointwise_parser = JsonOutputParser(pydantic_object=PointwiseScore)
        self.pairwise_parser = JsonOutputParser(pydantic_object=PairwiseVerdict)

    def _get_model(self) -> BaseChatModel:
        """Get LLM with API keys for judge evaluation."""
        # Infer provider from model name and available keys
        provider = None
        mn = (self.model_name or "").lower()

        # Priority: Explicit key > Model name inference
        if self.openrouter_api_key:
            provider = "openrouter"
        elif self.nvidia_api_key or mn.startswith("nvidia/"):
            provider = "nvidia"
        elif self.groq_api_key or ("/" not in mn):
            provider = "groq"

        return get_llm(
            model_name=self.model_name,
            provider=provider,
            openrouter_api_key=self.openrouter_api_key,
            nvidia_api_key=self.nvidia_api_key,
            groq_api_key=self.groq_api_key,
            temperature=0.0,  # Deterministic grading
        )

    async def evaluate_pointwise(
        self, metric: str, question: str, answer: str, context: str = "No context provided."
    ) -> Dict[str, Any]:
        """
        Runs a single G-Eval metric.
        """
        defn = METRICS.get(metric.lower())

        if not defn:
            return {
                "score": 0,
                "reasoning": f"Unknown metric: {metric}",
                "passed": False,
                "metric_name": metric,
            }

        pointwise_template = prompt_manager.get_template("eval", "pointwise_prompt")
        prompt = ChatPromptTemplate.from_messages(
            [("system", "You are a precise AI Judge."), ("human", pointwise_template)],
            template_format="jinja2",
        )

        llm = self._get_model()
        chain = prompt | llm | self.pointwise_parser

        try:
            result = await chain.ainvoke(
                {
                    "metric_name": metric.capitalize(),
                    "criteria_description": defn["desc"],
                    "scoring_steps": defn["steps"],
                    "question": question,
                    "answer": answer,
                    "context": context[:10000],
                }
            )

            passed = result["score"] >= 3

            return {
                "score": result["score"],
                "reasoning": result["reasoning"],
                "passed": passed,
                "metric_name": metric,
            }
        except Exception as e:
            log.error(f"Pointwise eval failed for {metric}: {e}")
            return {"score": 0, "reasoning": str(e), "passed": False, "metric_name": metric}

    async def compare_pairwise(
        self, question: str, response_a: str, response_b: str, metric: str = "helpfulness"
    ) -> Dict[str, Any]:
        """
        Compares two responses.
        """
        defn = METRICS.get(metric.lower()) or METRICS["helpfulness"]

        pairwise_template = prompt_manager.get_template("eval", "pairwise_prompt")
        prompt = ChatPromptTemplate.from_messages(
            [("system", "You are a precise AI Judge."), ("human", pairwise_template)],
            template_format="jinja2",
        )

        llm = self._get_model()
        chain = prompt | llm | self.pairwise_parser

        try:
            result = await chain.ainvoke(
                {
                    "metric_name": metric.capitalize(),
                    "criteria_description": defn["desc"],
                    "question": question,
                    "response_a": response_a,
                    "response_b": response_b,
                }
            )
            return result
        except Exception as e:
            log.error(f"Pairwise eval failed: {e}")
            return {"winner": "Tie", "reasoning": f"Error: {e}"}


# Default singleton (backward compatibility - uses env vars)
judge_service = LLMJudge()
