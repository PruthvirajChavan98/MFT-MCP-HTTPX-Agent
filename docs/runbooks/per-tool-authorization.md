# Per-Tool Authorization Runbook (GD6)

This runbook covers the authorization layer enforced at every authenticated
MCP tool boundary. For the inline LLM guard that filters noisy attack
phrasings before the tool is ever reached, see `inline_guard.py`. For the
admin-side auth flow, see [admin-enrollment.md](./admin-enrollment.md).

The guard is defence-in-depth. This layer is load-bearing — if it fails,
cross-session data access is possible regardless of what the guard blocks.

---

## 1. What the layer enforces

Three explicit contracts, each in its own module:

1. **`auth_state == "authenticated"`** — `validate_otp` writes this flag +
   `customer_id` to the Redis session on successful CRM login
   (`backend/src/mcp_service/auth_api.py`). No tool runs until the flag
   is present.
2. **Typed `SessionContext`** —
   `backend/src/mcp_service/session_context.py`. A frozen dataclass view
   over the raw session dict; exposes `session_id`, `customer_id`,
   `phone_number`, `access_token`, `loans: tuple[LoanRef, ...]`,
   `app_id: str | None`, `user_details` (read-only `MappingProxy`). Tools
   read from this instead of dict-digging, so a typo or a schema drift
   shows up at the type layer instead of silently leaking.
3. **Ownership verification at the boundary** —
   `backend/src/mcp_service/ownership.py`.
   - `verify_loan_ownership(ctx, loan_number, tool=...)` — the only
     place `loan_number in session.loans` is checked. `select_loan`
     routes through this.
   - `active_loan_or_raise(ctx, tool=...)` — returns the `LoanRef`
     matching `ctx.app_id`, re-verifying the pointer is still a member
     of `ctx.loans`. Tools that read the selected loan
     (`loan_details`, `foreclosure_details`, `overdue_details`,
     `noc_details`, `repayment_schedule`, `download_welcome_letter`,
     `download_soa`) route through this.
   - Both raise `OwnershipError(message, reason, tool)`, which
     increments the `agent_ownership_rejections_total{tool,reason}`
     Prometheus counter.

The decorator that glues the three together lives in
`backend/src/mcp_service/auth_decorators.py`.

---

## 2. Request flow (happy path and rejection paths)

```
LLM tool call
    │
    ▼
inline_guard.evaluate_prompt_safety_decision   (pre-tool — separate layer)
    │  allow
    ▼
FastMCP dispatch → public signature (…, session_id: str)
    │
    ▼
@requires_authenticated_session wrapper
    ├─ session_id blank / None ───────────► AUTH_REJECT_MESSAGE
    ├─ session not in Redis ──────────────► AUTH_REJECT_MESSAGE
    ├─ session.auth_state ≠ "authenticated" ► AUTH_REJECT_MESSAGE
    ├─ SessionContext.from_session_dict raises ► AUTH_REJECT_MESSAGE
    └─ writes _last_tool + _last_touch_ts audit marker
    │
    ▼
Inner tool body receives ctx: SessionContext
    │
    ├─ active_loan_or_raise(ctx) or
    │  verify_loan_ownership(ctx, loan_number)
    │      ├─ ownership rejection ─────────► return err.message
    │      └─ LoanRef
    │
    ▼
CRM call via MockFinTechAPIs(ctx.session_id)   (bearer token from session)
```

Two strings are surfaced to the LLM and, in turn, to the end user:

- `AUTH_REJECT_MESSAGE` — `"Please log in first. Use the generate_otp
  tool to start the login flow, then validate_otp with the code you
  received."`
- Ownership rejection — `"That loan doesn't appear on your account.
  Please use list_loans to see your available loans and then
  select_loan with the correct loan number."`

Both are deliberately agent-friendly: the LLM reads them and responds in
natural language without leaking the internal reason code.

---

## 3. Adding a new authenticated MCP tool

**Checklist.** Every box must be ticked before the tool merges.

- [ ] The tool wears `@requires_authenticated_session` (from
      `.auth_decorators`) **between** `@mcp.tool(...)` and the function
      body. Order matters — `@mcp.tool` outermost, decorator inner.
- [ ] The function's last parameter is `ctx: SessionContext`. The
      decorator rewrites the public MCP-facing signature so
      `session_id: str` replaces `ctx` — FastMCP's schema introspection
      sees `session_id`, which is what MCP clients send over the wire.
- [ ] If the tool consumes the active loan, it calls
      `active_loan_or_raise(ctx, tool="<name>")` and catches
      `OwnershipError` into a returned error string.
- [ ] If the tool takes an explicit `loan_number` argument, it calls
      `verify_loan_ownership(ctx, loan_number, tool="<name>")`.
- [ ] `AUTHENTICATED_TOOLS` in
      `backend/tests/test_mcp_tool_authorization_corpus.py` has a new
      tuple for the tool. CI runs
      `test_every_decorated_server_tool_is_in_corpus` which fails if
      you forget.
- [ ] Tool description entry added to `tool_descriptions.yaml` if the
      tool surfaces to the LLM via `_d("<name>")`.

**Pre-auth exceptions.** `generate_otp`, `validate_otp`, and
`search_knowledge_base` deliberately do **not** wear the decorator.
They run before the session has `auth_state="authenticated"` (or, for
the KB tool, against public FAQ content). Never extend this list
without a security review — every addition widens the pre-auth surface
area.

---

## 4. Troubleshooting

| Symptom | Likely cause | Where to look |
|---|---|---|
| LLM responds "Please log in first" for a user who *just* authenticated | `validate_otp` returned 2xx but the session in Redis is missing `customer_id` (CRM response malformed) | `auth_api.py::validate_otp` logs; look for `OTP Validate Error` and CRM response shape |
| Same "Please log in first" after a page refresh | Redis evicted the session or the session TTL expired | `RedisSessionStore` keyspace; compare `session_id` in browser storage against `redis-cli keys '*'` |
| LLM says "That loan doesn't appear on your account" for a loan the user *does* own | `session.loans` in Redis is stale after a mid-session CRM change (new loan sanctioned, etc.) | Force re-login to refresh `loans`; consider a future `refresh_loans` tool |
| `agent_ownership_rejections_total` spike | Either an attack attempt OR a UX bug (user referencing an old loan_number they remember) | Grafana `agent_ownership_rejections_total{tool=...,reason=...}`; correlate by `reason`: `loan_not_owned` = cross-session or UX bug; `app_id_not_owned` = loans array drift |
| FastMCP schema shows the wrong params for a newly-decorated tool | Decorator order wrong (`@mcp.tool` must be outermost) or `ctx` parameter name misspelled | `inspect.signature(server.<tool>.fn)` vs `server.<tool>.parameters` |

### Log lines emitted by this layer

- `mcp_auth_decorator` — `auth decorator: reject tool=<name> sid=<...> reason=unauthenticated|missing_session|malformed_session`
- `mcp_ownership` — `ownership: deny tool=<name> customer=<id> requested=<ln> known=[...]`
- `mcp_ownership` — `ownership: app_id not in loans tool=<name> customer=<id> app_id=<ln> known=[...]`

### Metrics to watch

- `agent_ownership_rejections_total{tool,reason}` — Counter.
  Labels: `tool` (any authenticated tool name) × `reason` ∈
  `{missing_loan_number, loan_not_owned, no_active_loan,
  app_id_not_owned}`.
- `agent_pii_leak_suspicions_total{tool}` — Counter. Incremented once
  per *unique* foreign 10-digit sequence found in an authenticated
  tool's response (see §7). A sustained spike means either the CRM
  is leaking another customer's data or the tool legitimately returns
  phone-shaped non-PII strings — both worth knowing.

---

## 7. Output-side PII leak detector (TA4)

After the decorator lets a tool response through, the same wrapper
calls `scan_tool_response_for_pii` from
`backend/src/mcp_service/output_pii_scanner.py` on the returned
string. The scanner covers **four** PII classes and increments a
single Prometheus Counter labelled by `(tool, pii_class)`.

| Class   | Regex (compiled)                                       | Exempt source (`ctx.user_details`)                          |
|---------|--------------------------------------------------------|-------------------------------------------------------------|
| phone   | `(?<!\d)(\d{10})(?!\d)`                                | `ctx.phone_number` → canonical last-10-digits               |
| pan     | `\b([A-Z]{5}[0-9]{4}[A-Z])\b`                          | `pan` key, uppercased/stripped                              |
| aadhaar | `(?<!\d)(\d{4}\s?\d{4}\s?\d{4})(?!\d)`                 | `aadhaar` (full 12-digit) OR `aadhaar_last_4` (suffix match) |
| email   | `\b[\w.+\-]+@[\w\-]+\.[\w.\-]+\b`                      | `email` key, lowercased/stripped                            |

All four canonicalise case/whitespace before comparison so the
caller's own value is reliably exempt regardless of the shape the
CRM happens to return.

### How it fires

For every unique canonical match that is NOT the caller's own value,
the scanner:

- Emits a warning: `pii_scan: foreign_<class>_detected tool=<name>
  caller=<customer_id> hits=<N>`.
- Increments `agent_pii_leak_suspicions_total{tool=<name>,
  pii_class=<class>}` by N (N = number of unique foreign matches in
  that class for that call).

**Never blocks the response.** Detection only. Operators review
metric spikes and decide whether to (a) fix the upstream CRM leak,
or (b) allow-list the `(tool, pii_class)` pair if the false positive
is structural (e.g. a loan application number shaped like a PAN).

### Known false-positive patterns to watch for

- **Phone**: none significant — 10-digit word-bounded runs are rare
  outside PII. Possible false hits: 10-digit tracking numbers.
- **PAN**: any 10-char string matching `AAAAA9999A` with any
  meaning. Rare in loan / CRM responses but monitor the
  `pii_class="pan"` counter for structural hits.
- **Aadhaar**: any 12-digit run bounded by non-digits — timestamps
  with microseconds `YYYYMMDDHHMMSSS` are filtered out by the
  non-digit boundary requirement, but a literal 12-digit transaction
  ID WOULD match. Very rare; if seen, add `aadhaar_last_4` to the
  session so legitimate caller-owned values exempt cleanly.
- **Email**: simplified pattern misses exotic valid emails (quoted
  local parts, IP-literal domains). Over-permissive on the other
  end: anything `@` between word chars + dot fires. Watch for
  `noreply@example.com`-style service emails baked into templates
  and allow-list by tool if structural.

### Adding an allow-list

Edit `_PII_CLASSES` in `output_pii_scanner.py` to short-circuit the
class's `is_exempt` function for specific `(tool_name, canonical)`
tuples. Alternatively, mute the alert in Grafana if the structural
noise is tolerable. Either way, document the decision in the PR
updating this runbook.

### Adding a new authenticated tool

Nothing to do — the decorator runs the scanner on every
authenticated response, and every PII class checks unconditionally.
Revisit only if your tool legitimately returns one of the patterns.

---

## 5. Rollback

The change is additive (new Redis fields + new decorator + new helpers
+ refactored server.py). Redis is schema-less, so existing sessions
lacking `customer_id`/`auth_state` naturally fail the decorator's
check and the user re-authenticates — no data migration.

To revert:

```bash
git revert <gd6-commit-sha>
```

The revert restores the implicit-identity session shape and the
pre-TA1 tool signatures. Session data rolls over naturally on the
next login cycle (< 24 h in practice given the TTL).

---

## 6. Regression coverage

56 tests anchor this layer:

- `backend/tests/test_session_context.py` (15) — frozen-dataclass
  contract, factory validation.
- `backend/tests/test_auth_decorator.py` (13) — signature rewriting,
  rejection paths, audit-trail marker.
- `backend/tests/test_ownership.py` (9) — ownership helpers,
  cross-session denial, tamper detection.
- `backend/tests/test_validate_otp_writes_customer_id.py` (3) — the
  identity-anchor write at login time.
- `backend/tests/test_mcp_tool_authorization_corpus.py` (57) —
  per-tool integration corpus: 12 tools × 3 reject scenarios + 7
  `tampered_app_id` + 13 happy-path + cross-session + catalogue
  completeness.

Keep this corpus green. Any attempt to loosen one of the rejection
strings or the decorator's behaviour should come with a new corpus
entry proving the new behaviour is intentional.
