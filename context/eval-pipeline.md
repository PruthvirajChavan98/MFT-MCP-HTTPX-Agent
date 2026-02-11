```markdown
# Evaluation Pipeline

## Shadow Eval Flow
```
Request → ShadowEvalCollector captures:
  - Tool calls (start/end)
  - Reasoning tokens
  - Final output
  - System prompt, chat history, tool definitions

→ maybe_shadow_eval_commit():
    ├─ should_shadow_eval()
    │   ├─ SHADOW_EVAL_ENABLED == "1"?
    │   ├─ random() <= SHADOW_EVAL_SAMPLE_RATE?
    │   └─ throttle: < SHADOW_EVAL_MAX_PER_MIN?
    │
    ├─ compute_non_llm_metrics()
    │   ├─ AnswerNonEmpty
    │   ├─ StreamOk
    │   └─ Rule-based: ToolMatch, NormalizedRegexMatch
    │
    ├─ compute_llm_metrics() (if ENABLE_LLM_JUDGE)
    │   └─ G-Eval pointwise: relevance, helpfulness, faithfulness, correctness, coherence
    │       via LLMJudge (default: openai/gpt-4o)
    │
    └─ Commit: Neo4j (trace+events+evals) + embeddings (vector search)
```

## Eval API Endpoints
| Endpoint | Purpose |
|---|---|
| `POST /eval/ingest` | External trace ingest (with auth) |
| `GET /eval/search` | Paginated trace search with metric filters |
| `GET /eval/sessions` | Session listing with aggregates |
| `GET /eval/trace/{id}` | Full trace with compressed events |
| `GET /eval/fulltext` | Fulltext search across events/traces/results |
| `POST /eval/vector-search` | Semantic search with per-field filters |
| `GET /eval/metrics/summary` | Metric aggregates + overall pass rate |
| `GET /eval/metrics/failures` | Failed evaluations listing |
| `GET /eval/question-types` | Router reason distribution |

## Docker Compose Config (current)
```yaml
SHADOW_EVAL_ENABLED: "1"
SHADOW_EVAL_SAMPLE_RATE: "1.0"   # 100% sampling!
SHADOW_EVAL_CAPTURE: "full"       # All tokens captured
```