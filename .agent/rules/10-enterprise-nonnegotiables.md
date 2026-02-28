# Enterprise Non-Negotiables

> These rules are **mandatory** and override all other guidance. No exceptions.

## Execution Philosophy

1. **No patchwork**. Every change must be durable, production-grade, and architecturally sound.
2. **Plan first**. Always produce a clear plan before implementation. Do not start coding until the user approves.
3. **Research-backed decisions**. Verify external APIs, libraries, and breaking changes against current documentation before coding.
4. **If unsure, stop**. If latest references cannot be verified, explicitly report the gap — do not guess.

## Implementation Quality Bar

- Align with all `.agent/rules/` standards (backend, frontend, testing, security, deployment).
- Include **migration-safe** updates across all dependent files — no orphan imports, no dead references.
- Add or update tests for every changed behavior. Run `make test` and report results.
- Report what was verified (research + tests) and what remains unverified.

## Change Impact Awareness

Before making any change, assess:

1. **Who calls this code?** Trace all callers — endpoints, workers, tests.
2. **What config does it touch?** Any new env vars must go in `core/config.py` and all compose files.
3. **Does it affect the API contract?** SSE event types, REST schemas, and GraphQL types are public contracts.
4. **Does it affect Docker?** New dependencies → rebuild images. New services → update compose files.
5. **Does it affect security?** Any auth/session/rate-limit change must be reviewed against the security rules.

## Git & Changelog

- Commit messages must be descriptive and imperative (e.g., "Add session init endpoint with UUIDv7").
- Significant changes must be documented in `CHANGELOG.md`.
- Never commit `.env`, secrets, API keys, or database dumps.

## Production Readiness Checklist

Before any deployment-affecting change:

- [ ] All existing tests pass (`make test`)
- [ ] New behavior has test coverage
- [ ] Code quality passes (`make quality`)
- [ ] Docker compose validates (`make local-validate`)
- [ ] No hardcoded secrets or URLs
- [ ] Resource limits defined for any new containers
- [ ] Health checks defined for any new services
- [ ] CHANGELOG.md updated for significant changes
