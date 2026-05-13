## Why

The codebase ships unit, e2e, contract, and integration test tiers — but several "contracts" are green on paper without enforcing the parity they claim. A test-quality audit found:

1. **Outbox contract suite never exercises the real adapter.** `outbox/tests/contracts/test_outbox_port_contract.py` claims dual-binding ("runs against both the fake and `SessionSQLModelOutboxAdapter` when a Postgres engine is available") but every test calls `_fake()` directly.
2. **`AuthorizationContract` claims dual-binding but is SQLModel-only.** No `FakeAuthorizationAdapter` exists.
3. **`UserAuthzVersionPortContract` only asserts "doesn't raise".** A silent `pass` in `bump()` still passes the contract.
4. **Rate-limiter implementations have divergent semantics with no parity contract.** `FixedWindowRateLimiter` is fixed-window; `RedisRateLimiter` is sliding-window. `FixedWindowRateLimiter` has zero direct unit tests.
5. **`FakeEmailPort` skips registry validation.** Auth e2e cannot detect a missing template registration.
6. **`FakeJobQueue` skips known-jobs check by default.** Production `InProcessJobQueueAdapter` always validates.
7. **`tests/integration/test_arq_round_trip.py` is marked `integration` but uses `fakeredis`.** Misleading marker.
8. **Auth e2e replaces the real outbox with `InlineDispatchOutboxAdapter`.** The outbox seam is never exercised end-to-end. No relay-idempotency regression test exists.
9. **Doc/code skip-env-var mismatch.** `CLAUDE.md` says `KANBAN_SKIP_TESTCONTAINERS=1`; some `conftest.py` files read `AUTH_SKIP_TESTCONTAINERS=1`.
10. **`users` feature `/me` GET/PATCH/DELETE has zero e2e coverage.** `features/users/tests/e2e/` contains only `__init__.py`.
11. **`PrincipalCachePort` has no contract test.** Both in-process and Redis variants are wired in production; neither is exercised against a shared contract.

## What Changes

- Implement real dual-binding contracts (parametrize over fake and real adapter) for: outbox, authorization, rate limiter, principal cache, email (registry-aware).
- Add a `FakeAuthorizationAdapter` (`src/features/authorization/tests/fakes/fake_authorization_adapter.py`) and strengthen `UserAuthzVersionPortContract` with a `read_version` probe.
- Make `FakeEmailPort` registry-aware (raises `UnknownTemplateError`).
- Make `FakeJobQueue.known_jobs` default to "raise on unknown".
- Re-mark `tests/integration/test_arq_round_trip.py` as `unit` (it uses `fakeredis`); add `tests/integration/test_arq_redis_round_trip.py` against `testcontainers`.
- Add `src/features/authentication/tests/integration/test_auth_flow_real_outbox.py` (real `SessionSQLModelOutboxAdapter` + one relay tick).
- Add `test_relay_skips_already_dispatched` and `test_relay_redispatches_after_simulated_crash` to outbox integration tests.
- Populate `src/features/users/tests/e2e/` with TestClient tests for `GET/PATCH/DELETE /me`.
- Drop the `AUTH_SKIP_TESTCONTAINERS` alias entirely (no deprecation cycle). Search-and-replace to `KANBAN_SKIP_TESTCONTAINERS` (the canonical name per `CLAUDE.md`); update any documentation.

**Capabilities — Modified**: `quality-automation`.

## Impact

- **Code**: only test code + a few fakes + minor docs (`CLAUDE.md`, any conftests under `src/features/*/tests/integration/`).
- **Migrations**: none.
- **CI**: net runtime increase is a few seconds when Docker is up; same time when Docker is unavailable.
- **Production**: none directly — but the new tests guard future correctness changes (`fix-outbox-dispatch-idempotency`, `make-auth-flows-transactional`, `harden-rate-limiting`).
