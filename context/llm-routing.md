# LLM Provider Routing

## `get_llm()` Decision Chain

```
Input: model_name, openrouter_api_key, nvidia_api_key, reasoning_effort

1. NVIDIA? (if nvidia key present)
   ├─ model starts with "nvidia/" → ChatNVIDIA
   ├─ "moonshot" in model → ChatNVIDIA
   ├─ "gpt-oss" in model → ChatNVIDIA
   ├─ "deepseek" + "r1" in model → ChatNVIDIA
   ├─ "llama" + "nvidia" in model → ChatNVIDIA
   └─ explicit nvidia_api_key → ChatNVIDIA

2. Groq? (if not NVIDIA)
   ├─ no "/" in model name → ChatGroq
   ├─ starts with "groq/" → ChatGroq
   └─ no openrouter key but groq keys available → ChatGroq
   Key cycling: itertools.cycle(GROQ_API_KEYS)
   Reasoning: gpt-oss→parsed, qwen→parsed, deepseek→raw

3. OpenRouter (fallback)
   └─ ChatDeepSeek with OpenRouter base URL
   Reasoning: enabled for streaming, disabled otherwise
```

## BYOK Cascade
```
request.openrouter_api_key  →  saved_config["openrouter_api_key"]  →  env OPENROUTER_API_KEY
request.nvidia_api_key      →  saved_config["nvidia_api_key"]      →  env NVIDIA_API_KEY