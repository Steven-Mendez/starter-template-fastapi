## Context

The template's testing strategy promises a Russian-doll pattern: unit (fast, fake adapters) → contract (same scenarios against real and fake) → e2e (HTTP) → integration (real DB/Redis/S3 via testcontainers). The pattern is right; the implementation has gaps where contracts are skipped against real adapters, fakes are too permissive, or "integration" is `fakeredis` in disguise. Each gap silently invalidates future correctness fixes.

This proposal changes only what we test and how aggressively the fakes match the real adapters. No production code is modified.

## Goals / Non-Goals

**Goals**
- "Contract test" means: the same scenario class runs against every implementation of a port — fake AND real — via parametrization, not via duplicated files.
- Fakes never silently relax constraints that the real adapter enforces (template registry, known-jobs).
- Every port with more than one production implementation has a contract suite exercising all of them.
- Integration markers reflect real-backend usage.

**Non-Goals**
- 100% line/branch coverage (existing 80/60 gates stay).
- Performance/load testing.
- Rewriting the existing pyramid.

## Decisions

### Decision 1: Parametrize, don't duplicate

Every contract suite is a single class whose scenarios run against every implementation via `pytest.mark.parametrize` or a fixture-scoped binding. Skip-aware when Docker is unavailable. Rejected: separate `..._contract_fake.py` and `..._contract_real.py` files — that drift is exactly what produced the current "fake-only" outbox suite.

### Decision 2: Fakes are strict by default; permissive mode is opt-in

`FakeEmailPort` requires a registry and raises `UnknownTemplateError`. `FakeJobQueue.known_jobs` defaults to "raise on unknown". Callers that want a wide-open fake pass `permissive=True` explicitly.

### Decision 3: Strengthen `UserAuthzVersionPortContract` with a probe method

Add `read_version(user_id)` to the port (already needed conceptually for the principal-cache staleness check). The contract asserts that `bump(...)` causes the next `read_version(...)` to return a strictly greater number.

### Decision 4: One canonical skip env var — `KANBAN_SKIP_TESTCONTAINERS`

Per `CLAUDE.md` the canonical skip env var is `KANBAN_SKIP_TESTCONTAINERS`. The `AUTH_SKIP_TESTCONTAINERS` alias used in some `conftest.py` files is dropped without deprecation. Rationale: aliases create confusion — `CLAUDE.md` already drifted once because of the alias. Tasks include a repo-wide search-and-replace step.

## Risks / Trade-offs

- Strict-fake defaults may break tests that relied on permissive defaults. Mitigation: every affected test is in the same repo; we fix them in the same PR.
- Parametrized contracts run slower (real-adapter parametrizations skip cleanly when Docker is absent). Net CI cost: a few seconds per PR.

## Migration Plan

Single PR. Order:

1. Strict-fake defaults + `FakeAuthorizationAdapter` (new module).
2. Outbox + Authorization + RateLimiter + PrincipalCache contracts parametrized.
3. `users` `/me` e2e suite.
4. Outbox real-adapter e2e + relay-idempotency regressions.
5. arq marker fix + new real-Redis test.
6. Skip env-var search-and-replace (`AUTH_SKIP_TESTCONTAINERS` → `KANBAN_SKIP_TESTCONTAINERS`).
7. Doc updates (`CLAUDE.md`).

Rollback: revert. No persistence side effects.

## Depends on

- None hard. Composes with `make-authz-grant-atomic` (adds `bump_in_session` to the same port that gets the `read_version` probe here), `harden-rate-limiting` (rate-limit + principal-cache contracts protect the new defaults), `fix-outbox-dispatch-idempotency` (relay-idempotency regression tests sit on top of its dedup table).

## Conflicts with

- Shares `UserAuthzVersionPort` with `make-authz-grant-atomic`; shares rate-limit and principal-cache touch points with `harden-rate-limiting`; shares `tests/integration/test_arq_round_trip.py` baseline with no other change but the re-mark is destructive (file moves to `unit` marker). Shares `CLAUDE.md` updates with other quality changes — coordinate landing order.
