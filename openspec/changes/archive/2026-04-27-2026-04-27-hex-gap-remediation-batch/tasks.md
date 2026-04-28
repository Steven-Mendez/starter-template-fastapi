# Tasks: Hexagonal Gap Remediation Batch

**Change ID**: `2026-04-27-hex-gap-remediation-batch`

---

## Implementation Checklist

- [x] Add and enforce transaction-boundary semantics in repository/UoW paths.
- [x] Move patch no-op validation into application handlers and map to HTTP 422.
- [x] Introduce direct query-side card lookup and remove board-scan query path.
- [x] Harden ApplicationError -> HTTP mapping with explicit exhaustive contract.
- [x] Include machine-readable `code` in problem details for application errors.
- [x] Remove hardcoded health backend literal from router; source from settings.
- [x] Add configurable write API-key protection for mutating routes only.
- [x] Enforce coverage gate in CI and align tooling guardrail tests.
- [x] Refactor integration fixture boot path to `create_app(...)` lifespan flow.
- [x] Map missing dependency container path to explicit 503 problem response.
- [x] Add fallback mapping for unmapped domain errors.
- [x] Encapsulate board column addition via explicit domain intent method.
- [x] Inject query handlers with a read-only query adapter view.

## Verification

- [x] `uv run pytest -m "not e2e"`
- [x] Targeted unit/integration tests for each capability pass.

## Remaining Follow-ups (separate changes)

- [x] Add optimistic locking/versioning and DB-level ordering constraints (tracked in `2026-04-27-persistence-concurrency-constraints`).
- [x] Continue aggregate encapsulation beyond column-add path (tracked in `2026-04-27-aggregate-encapsulation-phase2`).
