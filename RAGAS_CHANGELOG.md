# RAGAS Changelog

> Fetched from [github.com/explodinggradients/ragas/releases](https://github.com/explodinggradients/ragas/releases)
> on 2026-04-02. Covers **v0.2.0 → v0.4.3** (latest at time of fetch).
> Knowledge cutoff for prior versions: August 2025.

---

## v0.4.3 — 2025-01-13

- Added `DSPyOptimizer` with `MIPROv2` for advanced prompt optimization
- Added llms.txt generation for LLM-friendly documentation
- Implemented DSPy caching functionality
- Added system prompt support for `InstructorLLM` and `LiteLLMStructuredLLM`
- Enabled `FactualCorrectness` language adaptation
- Resolved `DiskCacheBackend` pickling issue with `InstructorLLM`
- Fixed lazy initialization of `DEFAULT_TOKENIZER` to avoid startup network calls
- Updated `DiscreteMetric` LLM examples to match current API
- Added repository parameter to checkout action for fork PR support

---

## v0.4.2 — 2024-12-23

- Migrated `SQLSemanticEquivalence`, `DataCompyScore`, `CHRF Score`, `QuotedSpans`, `MultiModalFaithfulness`, `MultiModalRelevance` to collections API
- Added AG-UI Protocol Integration for Agent Evaluation
- Added support for new `google-genai` SDK with backwards compatibility
- Added `generate_with_chunks` for pre-chunked documents
- Added HuggingFace tokenizer support in knowledge graph operations
- Added caching support for metrics collections and embeddings
- Added offline Mermaid support to PDF export / documented PDF export workflow
- Fixed `TopicAdherence` classification array length mismatch
- Fixed `Dict` type validation errors using `instructor Mode.JSON`
- Fixed `BasePrompt.adapt()` structured output guidance
- Fixed async client detection in instructor-wrapped LiteLLM routers
- Deprecated legacy metrics
- Replaced `OpenAI` with `AsyncOpenAI` in AG-UI
- Handled nested dicts/lists in `ToolCallF1` args

---

## v0.4.1 — 2024-12-10

- Added `save`/`load` methods to `BasePrompt`
- Added Anthropic and Gemini clients for custom client configuration
- Migrated `ToolCallAccuracy`, `ToolCallF1`, `TopicAdherence`, `AgentGoalAccuracy`, Rubrics metrics to collections API
- Replaced `embed_text()` with `aembed_text()` in `AnswerRelevancy`
- Added new `LLM_CONTEXT` input parameter for `TestsetGenerator`
- Added `run_config` guide to use collections API
- Organized integrations nav into collapsible groups

---

## v0.4.0 — 2024-12-03

**Breaking: major rebranding + modular `BasePrompt` architecture migration**

- Migrated all core metrics to modular `BasePrompt` architecture:
  `ContextPrecision`, `ContextRecall`, `ContextEntityRecall`, `AnswerRelevancy`,
  `ResponseGroundedness`, `AnswerAccuracy`, `Faithfulness`, `AnswerCorrectness`,
  `SummaryScore`, `FactualCorrectness`, `NoiseSensitivity`
- Added dual adapter support: Instructor + LiteLLM via `instructor.from_provider`
- Added support for GPT-4o, o-series models with automatic `temperature`/`top_p` constraint handling
- Added migration guide for v0.4
- Fixed `InstructorLLM` detection bug
- Fixed `MultiTurnSample` user_input validation logic
- Fixed automatic embedding provider matching for LLMs
- Fixed async client detection in instructor-wrapped LiteLLM routers
- Made `GitPython` an optional dependency
- Updated all customization how-to guides to collections API + LLM factory
- Made `GoogleEmbeddings` handle `GenerativeModel` clients
- Removed `AspectCritic` and `SimpleCriteria` legacy metrics

---

## v0.3.9 — 2024-11-11

- Migrated: `SummaryScore`, `NoiseSensitivity`, `Faithfulness`, `AnswerAccuracy`,
  `ContextRelevance`, `ContextPrecision`, `FactualCorrectness`, `ResponseGroundedness`,
  `ContextRecall` metrics (all now using collections API)
- Added metadata fields for synthetic data traceability
- Added documentation for `metrics.collections` API
- Created quickstart guide with interactive LLM and project structure
- Removed deprecated `ground_truths`, redundant `AnswerSimilarity` from collections API
- Updated documentation structure for experiments-first paradigm
- Made embeddings optional in `AnswerCorrectness` when using pure factuality mode
- Handled `max_completion_tokens` error for newer OpenAI models

---

## v0.3.8 — 2024-10-28

- Migrated: `SemanticSimilarity`, `AnswerCorrectness`, `ContextEntityRecall`,
  `SimpleCriteria`, `RougeScore`, `AnswerRelevance` to collections API
- Added `AspectCritic` metric for coherence, harmfulness, maliciousness, correctness
- Added `ragas_examples` console scripts and quickstart cmd with templates
- Fixed uvloop detection to skip `nest_asyncio` patching
- Fixed `NameError` during LlamaIndex query engine evaluation
- Fixed tuple-formatted entities in `SingleHopSpecificQuerySynthesizer`
- Merged `instructor_llm_factory` with `llm_factory`
- Removed deprecation warnings for LLM and embedding wrappers

---

## v0.3.7 — 2024-10-14

- Migrated `RougeScore`, `AnswerRelevance`, `BleuScore`, `AnswerSimilarity`,
  and all string metrics to collections API
- Streamlined theme extraction from overlaps in `MultiHopSpecificQuerySynthesizer`
- Added `bypass_n` option to `LangchainLLMWrapper` for completion control
- Added missing `token_usage_parser` props for test generation methods
- Added `List[List[str]]` formats for overlapped items in theme extraction
- Added how-to guide for aligning LLM-as-Judge
- Added metric comparison testing infrastructure

---

## v0.3.6 — 2024-10-03

- Added CHRF score, `ToolCallF1`, `QuotedSpans` metrics
- Refactored Gemini to `genai` SDK
- Added metrics input flexibility and metric decorators with validation
- Added Azure token usage extraction; added `base_url` to `embedding_factory`
- Added `disallowed_special` on tiktoken encode
- Added OCI Gen AI Integration for Direct LLM Support
- Added save/load functionality for LLM-based metrics
- Added how-to guide for evaluating RAG agents; LlamaIndex agentic evals for Gemini
- Fixed temperature setting issues, `asyncio` handling, BLEU coroutine warning
- Fixed `generate_multiple` caching issue, metric inheritance patterns
- Fixed concurrent `ResponseRelevancy`; fixed `answer_relevancy` scoring to prevent false zero
- Fixed `TopicAdherenceScore` bitwise operations TypeError
- Fixed Numpy 3.13 compatibility issue
- Added deprecation warnings for legacy LLMs and Prompts
- Added DevPod configuration

---

## v0.3.5 — 2024-09-17

- Added how-to guide for text-to-SQL agent evaluation
- Improved async/executor functionality
- Optimized knowledge graph for large corpus
- Added telemetry; calculated OpenAI model costs
- Added Prompt Optimization Tutorial
- Added metric type checking; improved agent metrics code examples
- Resolved `TypeError` in `TopicAdherenceScore` bitwise operations
- Removed experimental meta properties; removed need for regex patterns

---

## v0.3.4 — 2024-09-10

- Reduced `find_indirect_clusters()` runtime through neighbourhood detection
- Fixed LangChain multiple batching handling
- Improved knowledge graph coverage for `default_transform()`
- Context precision documentation enhancements

---

## v0.3.3 — 2024-09-04

- Refactored `RagasEmbeddings` for backward compatibility
- Moved tracing from `experimental` to `ragas/integrations`
- Refactored LLM structure; added `InstructorLLM`
- Moved `prompts`, `datasets`, experimental metrics, `utils`/exceptions to main package
- Added `py.typed` marker file
- Retired `experimental` namespace entirely
- Optimised `FactualCorrectness` metric runtime by ~50%
- Fixed `BadRequestError` for OpenAI O1-series models
- Added cancellable task support
- Enhanced `knowledge graph flexibility` and `relationship builders`
- Discontinued v0.2 security release support
- Added analytics: CommonRoom, Scarf, reo.js

---

## v0.3.2 — 2024-08-19

- Added save/load for prompt objects
- Converted `AnswerSimilarity` to dataclass
- Migrated `experiment` and CLI from `experimental` to main package
- Added backend to main package; simplified `pyproject.toml`
- Moved examples to project root as installable package
- Added Python 3.13 target support
- Added pre-commit hooks; removed Black formatter
- Removed `Simulation` module
- Integrated Claude Code GitHub Workflow

---

## v0.3.1 — 2024-08-11

- Documentation hello-world improvements
- API change fixes in examples
- Added Google Drive backend for storing datasets
- Fixed experimental docs navigation and tutorial links
- Fixed `mkdocstrings` path configuration

---

## v0.3.0 — 2024-07-17

**Major release**

- LlamaIndex agentic integration
- Security fix: CVE-2025-45691 (Arbitrary File Read Vulnerability)
- Added `ragas_experimental` back into main
- Added `user_simulator`
- Added `ragas evals` CLI
- Added `llm_factory` and `embedding_factory`
- Added `AlignmentRate` metric
- Refactored experimental code from nbdev
- Documentation styling upgrades
- Monorepo cleanup; release scripts

---

## v0.2.15 — 2024-04-24

- AWS Bedrock integration support
- LlamaStack integration
- Griptape integration
- Single-hop query testset generation tutorial
- Benchmarking tutorial
- Enhanced error messaging for `NoiseSensitivity` metric
- Fixed broken documentation links for NVIDIA metrics
- `MultiTurnSample` validator enhanced for multiple tool calls
- Call-to-action for Ragas app

---

## v0.2.14 — 2024-03-04

- HTTP request-response logging with environment flag control
- Multi-turn conversation evaluation support
- NVIDIA end-to-end accuracy, relevance, and groundedness metrics
- Haystack LLM and embedding wrapper
- R2R integration
- `StatementGeneratorPrompt` instruction updates in faithfulness evaluation
- Fixed `SimpleCriteria` metric bugs
- Fixed `SingleHopQuerySynthesizer` preparation combinations
- Groundedness metric optimization with early retry breaking
- Knowledge graph relationship storage optimization
- NumPy dtype fixes with improved error messages

---

## v0.2.13 — 2024-02-04

- `LangGraph` integration with metadata preservation
- Haystack integration tutorial
- End-of-sequence token for WatsonX model family
- OpenHands integration for GitHub issue resolution
- Faithfulness prompt refinement to avoid single-quote issues
- Internal logging and tracing system improvements
- `ToolCallAccuracy` initialization parameter removal
- Unicode encoding error resolution in knowledge graph save/load

---

## v0.2.12 — 2024-01-21

- Token parser additions for Bedrock with Anthropic
- Fixed true positive / false positive calculation errors
- Optional `use_effective_order` parameter for BLEU score
- Fixed `LLMContextPrecisionWithReference` metric reference
- Output parser bug resolution
- Canonical URL additions to documentation

---

## v0.2.11 — 2024-01-14

- `pysbd` removal; replaced sentence segmentation
- Rubrics-based metrics fixes
- Instance-based metrics improvements
- `ToolCall` message enhancement for all argument types
- Evaluation annotation URL fetch method
- `Swarm` integration + tutorial
- `experiment_name` parameter option in `evaluate()`
- UTF-8 encoding for save/load operations
- NumPy invert error resolution
- Comprehensive broken link fixes

---

## v0.2.10 — 2024-01-08

- Comprehensive getting started guide
- Question generation efficiency improvement in `ResponseRelevancy`
- LlamaIndex testset generator bug fix
- New RAG evaluation tutorial
- LangChain v3 integration tutorial

---

## v0.2.9 — 2023-12-24

- Replaced NLTK BLEU with `sacrebleu`
- Exact match caching feature
- Temperature handling improvements
- HHEM divide-by-zero error fix
- `TrainConfig` import additions
- Non-LLM context recall distance measure fix
- Ragas caching documentation

---

## v0.2.8 — 2023-12-10

- Genetic algorithm-based optimizer
- Few-shot example optimizer feature
- Gemini model completion signal support in `LangchainLLMWrapper`
- Google Vertex AI custom `is_finished_parser` logic
- Annotated testset loading capability
- Metric training demo example

---

## v0.2.7 — 2023-12-06

- Removed critics and rubrics from examples
- Test-generation improvements; extended to non-English corpora
- Added output type support to metrics
- Implemented dataloader for annotated JSON files
- Enabled training of custom evaluators
- Fixed missing query qualifiers

---

## v0.2.6 — 2023-11-19

- Optimised `FactualCorrectness` — avoids `decompose_claims` in precision mode
- Added `testset` upload functionality
- Removed `MetricWithLLM` from `SemanticSimilarity`
- Improved default test generation
- Fixed `ZeroDivisionError` in `ToolCallAccuracy` with no arguments
- Added extraction limits to extractors

---

## v0.2.5 — 2023-11-12

- Unified `sentence_segmenter` usage
- `AspectCritic` with reference support
- LangGraph agent evaluation tutorials
- Persona generator documentation
- Fixed recall calculation in `FactualCorrectness`
- LLM configuration and cost tracking documentation

---

## v0.2.4 — 2023-11-07

- LlamaIndex support: testset generation and evaluation
- Batched execution capability
- Automatic persona generation
- Added epsilon values in denominators to prevent division by zero
- Enhanced embeddings support in `TestsetGenerator`

---

## v0.2.3 — 2023-10-29

- Multimodal evaluation support
- F-beta score metric
- Measured testset generator costs
- Improved `FactualCorrectness` efficiency for precision mode
- Fixed agent goal accuracy issues
- Fixed reference key errors in `LLMContextPrecisionWithoutReference`

---

## v0.2.2 — 2023-10-22

- Trace support in `EvaluationResult`
- Prompt instruction translation when adapting to different languages
- Improved `to_pandas()` in testset generation
- Added `max_token` limit error handling
- Improved JSON parsing for agentic failures

---

## v0.2.1 — 2023-10-16

- Updated Bedrock modules for LangChain v0.3.x compatibility
- Fixed callback propagation in `RagasOutputParser`
- Corrected parameter naming in testset generation docs
- Broken link fixes and quickstart enhancements

---

## v0.2.0 — 2023-10-14

**Major breaking release — Pydantic v2 migration + new evaluation API**

- Introduced `TopicAdherence`, `ToolCallAccuracy`, `SQLSemanticEquivalence`,
  `FactualCorrectness` metrics
- Migrated to Pydantic v2
- New `TestsetGenerator` implementation replaces experimental versions
- Transform engines for testset generation
- `mkdocs`-based documentation
- Support for callbacks, traces, and language adaptation of prompts
- New evaluation API: `EvaluationDataset`, `SingleTurnSample`, `MultiTurnSample`,
  `evaluate()` takes dataset object instead of raw dicts
- Metrics are class instances rather than imported functions
