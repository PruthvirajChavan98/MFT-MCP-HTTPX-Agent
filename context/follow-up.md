```markdown
# Follow-Up Question Generation

## Pipeline
```
1. CACHE CHECK
   └─ Neo4j vector search: FollowUpContext.embedding ≥ 0.92 similarity
   └─ Hit? Return cached questions immediately.

2. CONTEXT
   └─ Fetch related FAQs via graph_rag vector search (≥ 0.7 similarity)

3. GENERATE (streaming)
   └─ LLM generates 5 follow-up questions (JSON)
   └─ Streams: reasoning tokens → candidate questions → per-candidate "why"

4. JUDGE
   └─ LLM scores candidates: groundedness×0.3 + relevance×0.5 + correctness×0.2
   └─ Filter: score ≥ 7.0
   └─ Return top 3

5. CACHE RESULT
   └─ Store FollowUpContext + SuggestedQuestion nodes in Neo4j
```

## SSE Event Types
| Event | Data |
|---|---|
| `status` | Progress messages |
| `reasoning` | LLM reasoning tokens |
| `candidate` | `{id, question}` |
| `candidate_why_token` | `{id, token}` |
| `candidate_why_done` | `{id, why}` |
| `result` | Final judged list (JSON array) |
| `done` | `[DONE]` |
```