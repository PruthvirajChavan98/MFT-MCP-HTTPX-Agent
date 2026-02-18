#!/usr/bin/env python3
"""Run production endpoint checks and emit a markdown report."""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx


@dataclass
class TestCase:
    name: str
    method: str
    path: str
    headers: dict[str, str] | None = None
    params: dict[str, Any] | None = None
    json_body: Any | None = None
    data: dict[str, Any] | None = None
    files: dict[str, tuple[str, bytes, str]] | None = None
    stream: bool = False
    notes: str = ""


@dataclass
class TestResult:
    name: str
    method: str
    path: str
    status: str
    result: str
    notes: str
    preview: str


def _mask_secret(secret: str | None, keep: int = 4) -> str:
    if not secret:
        return ""
    if len(secret) <= keep * 2:
        return "*" * len(secret)
    return f"{secret[:keep]}...{secret[-keep:]}"


def _preview_text(text: str, limit: int = 700) -> str:
    compact = (text or "").replace("\r", "").replace("\n", "<br>")
    compact = compact.replace("|", "\\|")
    if len(compact) <= limit:
        return compact
    return compact[:limit] + " ..."


def _run_one(
    client: httpx.Client, base_url: str, tc: TestCase, timeout_seconds: float
) -> TestResult:
    url = f"{base_url.rstrip('/')}{tc.path}"
    try:
        if tc.stream:
            with client.stream(
                tc.method,
                url,
                headers=tc.headers,
                params=tc.params,
                json=tc.json_body,
                data=tc.data,
                files=tc.files,
                timeout=timeout_seconds,
            ) as resp:
                parts: list[str] = []
                total_chars = 0
                for line in resp.iter_lines():
                    if line is None:
                        continue
                    s = line.strip()
                    if not s:
                        continue
                    parts.append(s)
                    total_chars += len(s)
                    if total_chars >= 900:
                        break
                body_preview = "\n".join(parts)
                status = str(resp.status_code)
        else:
            resp = client.request(
                tc.method,
                url,
                headers=tc.headers,
                params=tc.params,
                json=tc.json_body,
                data=tc.data,
                files=tc.files,
                timeout=timeout_seconds,
            )
            status = str(resp.status_code)
            body_preview = resp.text
    except Exception as exc:  # noqa: BLE001
        return TestResult(
            name=tc.name,
            method=tc.method,
            path=tc.path,
            status="ERR",
            result="FAIL",
            notes="transport_error",
            preview=_preview_text(str(exc)),
        )

    try:
        is_pass = int(status) < 500
    except ValueError:
        is_pass = False

    return TestResult(
        name=tc.name,
        method=tc.method,
        path=tc.path,
        status=status,
        result="PASS" if is_pass else "FAIL",
        notes=tc.notes,
        preview=_preview_text(body_preview),
    )


def _build_test_cases(
    session_id: str,
    question: str,
    trace_id: str,
    groq_api_key: str,
    openrouter_api_key: str,
) -> list[TestCase]:
    faq_question = f"prod endpoint test faq {int(time.time())}"
    faq_answer = "This is a production endpoint test FAQ entry."

    tiny_pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"

    session_config = {
        "session_id": session_id,
        "model_name": "openai/gpt-oss-120b",
        "provider": "groq",
        "groq_api_key": groq_api_key,
        "reasoning_effort": "high",
    }

    agent_request = {
        "session_id": session_id,
        "question": question,
    }

    tests = [
        TestCase("health", "GET", "/health"),
        TestCase("health_live", "GET", "/health/live"),
        TestCase("health_ready", "GET", "/health/ready"),
        TestCase("metrics", "GET", "/metrics"),
        TestCase("agent_config_set", "POST", "/agent/config", json_body=session_config),
        TestCase("agent_config_get", "GET", f"/agent/config/{session_id}"),
        TestCase("agent_query", "POST", "/agent/query", json_body=agent_request),
        TestCase(
            "agent_stream",
            "POST",
            "/agent/stream",
            json_body=agent_request,
            stream=True,
            notes="stream",
        ),
        TestCase("follow_up", "POST", "/agent/follow-up", json_body=agent_request),
        TestCase(
            "follow_up_stream",
            "POST",
            "/agent/follow-up-stream",
            json_body=agent_request,
            stream=True,
            notes="stream",
        ),
        TestCase("sessions_list", "GET", "/agent/sessions"),
        TestCase("session_verify", "GET", f"/agent/verify/{session_id}"),
        TestCase("session_cost", "GET", f"/agent/sessions/{session_id}/cost"),
        TestCase("session_cost_history", "GET", f"/agent/sessions/{session_id}/cost/history"),
        TestCase("session_summary", "GET", "/agent/sessions/summary"),
        TestCase("session_cost_reset", "DELETE", f"/agent/sessions/{session_id}/cost"),
        TestCase("session_cleanup", "DELETE", "/agent/sessions/cleanup"),
        TestCase("models", "GET", "/agent/models"),
        TestCase(
            "router_classify",
            "POST",
            "/agent/router/classify",
            json_body={
                "session_id": session_id,
                "text": question,
                "openrouter_api_key": openrouter_api_key,
                "mode": "hybrid",
            },
        ),
        TestCase(
            "router_compare",
            "POST",
            "/agent/router/compare",
            json_body={
                "session_id": session_id,
                "text": question,
                "openrouter_api_key": openrouter_api_key,
            },
        ),
        TestCase("faqs_get", "GET", "/agent/admin/faqs", params={"limit": 100, "skip": 0}),
        TestCase(
            "faqs_batch_json",
            "POST",
            "/agent/admin/faqs/batch-json",
            json_body={"items": [{"question": faq_question, "answer": faq_answer}]},
            headers={"X-OpenRouter-Key": openrouter_api_key},
            stream=True,
            notes="stream",
        ),
        TestCase(
            "faqs_semantic_search",
            "POST",
            "/agent/admin/faqs/semantic-search",
            headers={"X-OpenRouter-Key": openrouter_api_key},
            json_body={"query": question, "limit": 5},
        ),
        TestCase(
            "faqs_semantic_delete",
            "POST",
            "/agent/admin/faqs/semantic-delete",
            headers={"X-OpenRouter-Key": openrouter_api_key},
            json_body={"query": faq_question, "threshold": 0.99},
        ),
        TestCase(
            "faqs_edit",
            "PUT",
            "/agent/admin/faqs",
            headers={"X-OpenRouter-Key": openrouter_api_key},
            json_body={"original_question": faq_question, "new_answer": faq_answer + " Edited."},
        ),
        TestCase(
            "faqs_delete_single", "DELETE", "/agent/admin/faqs", params={"question": faq_question}
        ),
        TestCase("all_followups", "GET", "/agent/all-follow-ups"),
        TestCase(
            "faqs_upload_pdf",
            "POST",
            "/agent/admin/faqs/upload-pdf",
            headers={"X-OpenRouter-Key": openrouter_api_key},
            files={"file": ("sample.pdf", tiny_pdf, "application/pdf")},
            stream=True,
            notes="stream",
        ),
        TestCase(
            "eval_ingest",
            "POST",
            "/eval/ingest",
            headers={"X-Eval-Ingest-Key": "invalid"},
            json_body={
                "trace": {
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "provider": "groq",
                    "model": "openai/gpt-oss-120b",
                    "endpoint": "/agent/query",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "status": "success",
                },
                "events": [],
                "evals": [],
            },
        ),
        TestCase("eval_search", "GET", "/eval/search", params={"limit": 20, "offset": 0}),
        TestCase("eval_sessions", "GET", "/eval/sessions", params={"limit": 20, "offset": 0}),
        TestCase("eval_trace", "GET", f"/eval/trace/{trace_id}"),
        TestCase(
            "eval_fulltext",
            "GET",
            "/eval/fulltext",
            params={"q": question, "kind": "event", "limit": 20, "offset": 0},
        ),
        TestCase(
            "eval_vector_search",
            "POST",
            "/eval/vector-search",
            headers={"X-OpenRouter-Key": openrouter_api_key},
            json_body={
                "kind": "trace",
                "text": question,
                "k": 10,
                "min_score": 0.0,
                "session_id": session_id,
            },
        ),
        TestCase("eval_metrics_summary", "GET", "/eval/metrics/summary"),
        TestCase(
            "eval_metrics_failures",
            "GET",
            "/eval/metrics/failures",
            params={"limit": 20, "offset": 0},
        ),
        TestCase("eval_question_types", "GET", "/eval/question-types", params={"limit": 200}),
        TestCase("graphql_get", "GET", "/graphql"),
        TestCase("graphql_post", "POST", "/graphql", json_body={"query": "{ __typename }"}),
        TestCase("rate_limit_health", "GET", "/rate-limit/health"),
        TestCase("rate_limit_config", "GET", "/rate-limit/config"),
        TestCase("rate_limit_metrics", "GET", "/rate-limit/metrics"),
        TestCase("rate_limit_status", "GET", f"/rate-limit/status/session_{session_id}"),
        TestCase("rate_limit_reset", "POST", f"/rate-limit/reset/session_{session_id}"),
        TestCase("faqs_delete_all", "DELETE", "/agent/admin/faqs/all"),
        TestCase("session_logout", "DELETE", f"/agent/logout/{session_id}"),
    ]

    return tests


def _render_report(
    base_url: str,
    session_id: str,
    groq_api_key: str,
    model_name: str,
    provider: str,
    reasoning_effort: str,
    results: list[TestResult],
) -> str:
    generated = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    passed = sum(1 for r in results if r.result == "PASS")
    failed = len(results) - passed

    lines = [
        "# Production Endpoint Test Report",
        "",
        f"- Generated: {generated}",
        f"- Target: `{base_url}` (docker-compose.yml production stack)",
        (
            "- Session config used: "
            f"`session_id={session_id}`, "
            f"`model_name={model_name}`, "
            f"`provider={provider}`, "
            f"`reasoning_effort={reasoning_effort}`, "
            f"`groq_api_key={_mask_secret(groq_api_key)}`"
        ),
        f"- Total endpoint checks: **{len(results)}**",
        f"- Passed (HTTP < 500 / no transport error): **{passed}**",
        f"- Failed: **{failed}**",
        "",
        "## Endpoint Results",
        "",
        "| # | Test | Method | Path | Status | Result | Notes | Response Preview |",
        "|---:|---|---|---|---:|---|---|---|",
    ]

    for idx, r in enumerate(results, start=1):
        lines.append(
            f"| {idx} | {r.name} | `{r.method}` | `{r.path}` | `{r.status}` | **{r.result}** | {r.notes} | {r.preview} |"
        )

    lines.append("")
    lines.append("## Observations")
    lines.append("")
    if failed == 0:
        lines.append("- All endpoint checks passed under the report pass criteria.")
    else:
        lines.append(
            "- One or more endpoint checks failed; inspect rows marked **FAIL** for details."
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run production endpoint checks and generate markdown report"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8005")
    parser.add_argument("--session-id", default="groq_test")
    parser.add_argument("--question", default="customer care")
    parser.add_argument("--model-name", default="openai/gpt-oss-120b")
    parser.add_argument("--provider", default="groq")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--groq-api-key", default=os.getenv("GROQ_API_KEY", ""))
    parser.add_argument("--openrouter-api-key", default=os.getenv("OPENROUTER_API_KEY", ""))
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--report", default="PRODUCTION_ENDPOINT_TEST_REPORT.md")

    args = parser.parse_args()

    trace_id = f"prod-test-{int(time.time())}"

    tests = _build_test_cases(
        session_id=args.session_id,
        question=args.question,
        trace_id=trace_id,
        groq_api_key=args.groq_api_key,
        openrouter_api_key=args.openrouter_api_key,
    )

    with httpx.Client(follow_redirects=True) as client:
        results = [_run_one(client, args.base_url, tc, args.timeout) for tc in tests]

    report = _render_report(
        base_url=args.base_url,
        session_id=args.session_id,
        groq_api_key=args.groq_api_key,
        model_name=args.model_name,
        provider=args.provider,
        reasoning_effort=args.reasoning_effort,
        results=results,
    )

    with open(args.report, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Wrote {args.report} with {len(results)} checks.")
    print(
        f"Passed: {sum(1 for r in results if r.result == 'PASS')} | Failed: {sum(1 for r in results if r.result == 'FAIL')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
