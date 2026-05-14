## 1. Outbox contract — real adapter

- [x] 1.1 Parametrize `src/features/outbox/tests/contracts/test_outbox_port_contract.py` over `(InMemoryOutboxAdapter, SessionSQLModelOutboxAdapter)`. Real-adapter binding uses the existing `postgres_outbox_engine` fixture; skip when Docker is unavailable.
- [x] 1.2 Assert commit/rollback semantics: outbox rows visible only after the surrounding transaction commits.
- [x] 1.3 Assert payload timezone handling (`available_at` round-trips correctly).

## 2. AuthorizationContract — dual-binding + fake

- [x] 2.1 Add `src/features/authorization/tests/fakes/fake_authorization_adapter.py` implementing the full `AuthorizationPort` Protocol in memory.
- [x] 2.2 Add `test_authorization_contract_in_memory.py` subclassing `AuthorizationContract` against the fake.
- [x] 2.3 Verify `test_authorization_contract_sqlmodel.py` still passes against the real adapter.

## 3. Strengthen `UserAuthzVersionPortContract`

- [x] 3.1 Extend `UserAuthzVersionPort` with a `read_version(user_id)` probe method.
- [x] 3.2 Add scenarios asserting `bump(...)` actually increments (vs. "returns Ok").
- [x] 3.3 Add an `AuditPortContract` scenario asserting `record(...)` is observable from a separate query (against both fake and real adapter).

## 4. RateLimiterContract

- [x] 4.1 Define `RateLimiterContract` with scenarios: allow N in-window; block N+1; recover after window passes; distinct keys are independent; explicit reset clears all.
- [x] 4.2 Parametrize over `(FixedWindowRateLimiter, RedisRateLimiter)`. Redis variant uses `fakeredis`; add an optional `testcontainers` Redis binding.

## 5. FakeEmailPort + FakeJobQueue tightening

- [x] 5.1 Make `FakeEmailPort` accept the registry and raise `UnknownTemplateError` on unregistered names. Add the registry check to the email contract.
- [x] 5.2 Update auth e2e conftest to pass the registry when constructing the fake.
- [x] 5.3 Change `FakeJobQueue.known_jobs` default to raise on unknown name; callers opt into permissive mode explicitly.
- [x] 5.4 Add an `enqueue_at` scenario to the `JobQueuePort` contract.

## 6. PrincipalCacheContract

- [x] 6.1 Define a contract: `set/get`, TTL expiry, `invalidate_user` removes the entry, miss-then-set round-trip.
- [x] 6.2 Parametrize over `(InProcessPrincipalCache, RedisPrincipalCache)`. Redis variant uses `fakeredis`.

## 7. Re-mark arq round-trip

- [x] 7.1 Re-mark `src/features/background_jobs/tests/integration/test_arq_round_trip.py` as `unit` (it uses `fakeredis`); move it under a `tests/unit/` path if existing markers also require relocation.
- [x] 7.2 Add `src/features/background_jobs/tests/integration/test_arq_redis_round_trip.py` against `testcontainers` Redis. Skip when Docker is unavailable.

## 8. End-to-end outbox in auth flows

- [x] 8.1 Add `src/features/authentication/tests/integration/test_auth_flow_real_outbox.py` using `SessionSQLModelOutboxAdapter` + one relay tick.
- [x] 8.2 Add `test_relay_skips_already_delivered` to outbox integration: pre-mark a row as `delivered` (post-`fix-outbox-dispatch-idempotency` state name), run the relay → assert no enqueue.
- [x] 8.3 Add `test_relay_redelivers_after_simulated_crash`: insert a row, run the relay with the queue raising once after the enqueue but before the commit, then again normally → assert exactly one effective handler invocation thanks to `__outbox_message_id` dedup.

## 9. Populate `users` feature e2e

- [x] 9.1 Add `src/features/users/tests/e2e/test_me.py` covering `GET /me`, `PATCH /me` (happy + invalid input), `DELETE /me` (self-deactivation).
- [x] 9.2 Include authentication-failure cases (unauthenticated, deactivated user).

## 10. Skip env-var alignment (drop the alias)

- [x] 10.1 Search the repo for `AUTH_SKIP_TESTCONTAINERS`: `rg -l AUTH_SKIP_TESTCONTAINERS src/`.
- [x] 10.2 Replace every occurrence with `KANBAN_SKIP_TESTCONTAINERS` (the canonical name per `CLAUDE.md`). No alias retained; no deprecation warning.
- [x] 10.3 Confirm `CLAUDE.md` already documents `KANBAN_SKIP_TESTCONTAINERS=1 make test-integration`; no doc change needed beyond that.

## 11. Wrap-up

- [x] 11.1 `make ci` green. (`make test` 749 passed; `make test-integration` 66 passed; `make quality` lint+arch+typecheck all green).
- [x] 11.2 `make test-integration` with Docker → confirm new real-adapter contract suites execute (not skipped).
- [x] 11.3 `KANBAN_SKIP_TESTCONTAINERS=1 make test-integration` → confirm they skip cleanly with a clear reason.
- [x] 11.4 `rg AUTH_SKIP_TESTCONTAINERS` returns zero hits.
