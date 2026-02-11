# Data Stores

## Redis (redis-stack-server)
No authentication. Shared by MCP + Agent.

### Key Patterns
| Key | Type | Owner | TTL |
|---|---|---|---|
| `{session_id}` | String (JSON) | MCP session_store | None |
| `agent:config:{session_id}` | Hash | ConfigManager | None |
| `agent:models:cache_all` | String (JSON) | ModelService | Overwritten every 30min |
| `eval:live` | Stream | eval_ingest | Capped at 50k entries |
| `router:jobs` | Stream + consumer group | shadow_eval → router_worker | Capped at 50k entries |

## Neo4j 5.26 (Community Edition)

### Constraints (all single-property — Community safe)
- `EvalTrace.trace_id` UNIQUE
- `EvalResult.eval_id` UNIQUE
- `EvalEvent.event_key` UNIQUE
- `Question.text` UNIQUE
- `Topic.name` UNIQUE
- `Product.name` UNIQUE
- `GroundingQuestion.text` UNIQUE

### Vector Indexes (all 1536-d, cosine)
| Index | Node Label | Property |
|---|---|---|
| `question_embeddings` | Question | embedding |
| `evaltrace_embeddings` | EvalTrace | embedding |
| `evalresult_embeddings` | EvalResult | embedding |
| `followup_context_embeddings` | FollowUpContext | embedding |
| `grounding_embeddings` | GroundingQuestion | embedding |

### Fulltext Indexes
| Index | Fields |
|---|---|
| `evalevent_text` | EvalEvent.text |
| `evaltrace_text` | EvalTrace.final_output, inputs_json |
| `evalresult_text` | EvalResult.metric_name, reasoning |