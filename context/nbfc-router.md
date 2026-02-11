# NBFC Router

## ⚠️ Two Versions Coexist

### v1: `router/service.py` + `router/worker.py`
- Pure Python cosine similarity (no numpy)
- Deployed as `router_worker` container consuming Redis Streams
- Writes to `EvalTrace.router_*` fields

### v2: `features/nbfc_router.py` (ACTIVE in agent)
- numpy-based cosine similarity
- Disk-cached prototype embeddings (`_ProtoCache`)
- Tone override system (profanity, pos/neg cues, foreclosure inquiry)
- Reason boosts via regex patterns
- Ambiguity detection (margin < 0.03 between top-2)
- `FORCE_LLM_RE` for high-stakes (fraud, harassment)
- Used directly by `/agent/stream` and `/agent/router/classify`

### Recommendation
Decommission v1. Stop `router_worker` container. Remove `router/` directory.

## Classification Pipeline (v2 Hybrid)
```
1. EmbeddingsRouter.classify(text)
   ├─ sentiment: cosine(query, prototypes) + tone_override()
   └─ reason: cosine(query, prototypes) + lexical boosts

2. Need LLM?
   ├─ FORCE_LLM_RE matches (fraud/harassment) → always LLM
   ├─ sentiment unknown/ambiguous/low-score → LLM
   └─ reason expected but unknown/ambiguous/low-score → LLM

3. LLMRouter.classify(text)
   └─ GLM-4.7 via ChatDeepSeek structured output
```

## Labels
- **Sentiment**: positive, neutral, negative, mixed, unknown
- **Reason** (16 categories): lead_intent_new_loan, eligibility_offer, loan_terms_rates, kyc_verification, otp_login_app_tech, application_status_approval, disbursal, emi_payment_reflecting, nach_autodebit_bounce, charges_fees_penalty, foreclosure_partpayment, statement_receipt, collections_harassment, fraud_security, customer_support, unknown
```