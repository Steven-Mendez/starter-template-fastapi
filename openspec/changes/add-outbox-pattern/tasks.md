## 1. Scaffolding and settings

- [x] 1.1 Create `src/features/outbox/` with the standard feature subtree (`domain/`, `application/`, `adapters/`, `composition/`, `tests/`) and per-subpackage `__init__.py` files
- [x] 1.2 Add `OutboxSettings` at `src/features/outbox/composition/settings.py` with fields `enabled: bool`, `relay_interval_seconds: float`, `claim_batch_size: int`, `max_attempts: int`, `worker_id: str` and a `from_app_settings(...)` constructor mirroring `JobsSettings`
- [x] 1.3 Implement `OutboxSettings.validate(errors)` (range checks: positive interval, positive batch size, positive max attempts) and `validate_production(errors)` (refuses `enabled=False`)
- [x] 1.4 Add `outbox_enabled`, `outbox_relay_interval_seconds`, `outbox_claim_batch_size`, `outbox_max_attempts`, `outbox_worker_id` fields to `AppSettings` (env prefix `APP_OUTBOX_`) with sensible defaults (`enabled=False`, `interval=5.0`, `batch=100`, `attempts=8`, `worker_id` computed as `f"{socket.gethostname()}:{os.getpid()}"` when unset)
- [x] 1.5 Include `OutboxSettings.validate` in `_validate_auth_settings` and `OutboxSettings.validate_production` in `_validate_production_settings` (codebase does not actually expose `settings.email`-style attribute properties; consumers call `<Settings>.from_app_settings(...)` directly)
- [x] 1.6 Update `src/platform/tests/test_settings.py` with cases asserting the production validator rejects `APP_OUTBOX_ENABLED=false` and accepts `APP_OUTBOX_ENABLED=true` (also added `_VALID_PROD_ENV["APP_OUTBOX_ENABLED"]="true"` so existing prod tests still pass, plus range checks for interval/batch/max-attempts)

## 2. Domain and application layer

- [x] 2.1 Add `src/features/outbox/domain/status.py` defining `OutboxStatus = Literal["pending", "dispatched", "failed"]`
- [x] 2.2 Add `src/features/outbox/domain/message.py` with a frozen `@dataclass` `OutboxMessage` (id, job_name, payload, available_at, status, attempts, last_error, locked_at, locked_by, created_at, dispatched_at)
- [x] 2.3 Add the inbound `OutboxPort` Protocol at `src/features/outbox/application/ports/outbox_port.py` with `enqueue(*, job_name, payload, available_at=None)`
- [x] 2.4 Add the outbound repository port at `src/features/outbox/application/ports/outbound/outbox_repository_port.py` defining `claim_batch(now, batch_size, worker_id) -> list[OutboxMessage]`, `mark_dispatched(ids, dispatched_at)`, `mark_retry(id, *, attempts, last_error, available_at)`, and `mark_failed(id, *, attempts, last_error)`
- [x] 2.5 Add `src/features/outbox/application/use_cases/dispatch_pending.py` implementing the relay tick: claim → for each row try `job_queue.enqueue(...)` → mark_dispatched/mark_retry/mark_failed; returns a `RelayTickReport(claimed=K, dispatched=N, retried=M, failed=F)` for observability
- [x] 2.6 Add application errors at `src/features/outbox/application/errors.py` (`OutboxDispatchError`)

## 3. SQLModel adapter and migration

- [x] 3.1 Add `src/features/outbox/adapters/outbound/sqlmodel/models.py` declaring `OutboxMessageTable` with the columns and indexes specified in `design.md` (`status` + `available_at` partial index `WHERE status='pending'`, `created_at` btree)
- [x] 3.2 Add `src/features/outbox/adapters/outbound/sqlmodel/adapter.py` with `SessionSQLModelOutboxAdapter` (session-scoped) implementing `OutboxPort.enqueue` by `session.add(OutboxMessageTable(...))` — MUST NOT commit
- [x] 3.3 Add `src/features/outbox/adapters/outbound/sqlmodel/repository.py` with `SQLModelOutboxRepository` (engine-scoped) implementing the outbound repository port; `claim_batch` issues `SELECT ... FOR UPDATE SKIP LOCKED` and the lock-update inside one short transaction
- [x] 3.4 Wrote the Alembic migration directly (`alembic/versions/20260515_0012_outbox_messages.py`) — autogenerate would need a running DB and would omit the partial index; the migration creates the table + `ix_outbox_pending` (partial, `status='pending'`) + `ix_outbox_created`
- [x] 3.5 Add `src/features/outbox/tests/fakes/fake_outbox.py` with `InMemoryOutboxAdapter` (collects rows in a list, exposes `commit()` / `rollback()` hooks; on `commit` dispatches each row to a stored `Callable[[str, dict], None]` dispatcher)

## 4. Composition wiring

- [x] 4.1 Add `src/features/outbox/composition/container.py` defining `OutboxContainer` (settings, port factory `session_scoped(session) -> OutboxPort`, dispatch_pending use case, shutdown hook) and `build_outbox_container(settings, *, engine, job_queue_port)`
- [x] 4.2 Add `src/features/outbox/composition/wiring.py` mirroring the other features (`attach_outbox_container`, `get_outbox_container`)
- [x] 4.3 Wire the outbox container in `src/main.py` between `jobs` and `authentication`; `outbox.session_scoped_factory` will be plumbed into `build_auth_container` in task 6.4 alongside the consumer migration (kept signature change in one place)
- [x] 4.4 Add Import Linter contracts to `pyproject.toml`: `outbox ↛ other features`, `outbox ↛ background_jobs.adapters`; also added `outbox.composition.settings` to platform-isolation ignores; `make lint-arch` → 19 kept, 0 broken. The `authentication ↛ background_jobs.adapters` contract from the proposal is deferred to task 6 once the consumer migration removes the existing legitimate import.

## 5. Worker relay registration

- [x] 5.1 Add `src/features/outbox/composition/worker.py` exposing `build_relay_cron_jobs(container) -> Sequence[cron]` (returns `[]` when `settings.enabled=False`, otherwise an arq `cron` snapped to the nearest divisor of 60 seconds with `run_at_startup=True, unique=True`)
- [x] 5.2 Update `src/worker.py` to build a SQLAlchemy engine + Redis client, construct the outbox container, and attach `build_relay_cron_jobs(outbox)` to `WorkerSettings.cron_jobs`
- [x] 5.3 Add `src/features/outbox/tests/unit/test_no_relay_in_web.py` asserting `src/main.py` does not import `build_relay_cron_jobs` (passes; guards the boundary at the source-text level so the worker stays the only scheduler)

## 6. Authentication issue-token-transaction surface (prerequisite for consumer migration)

- [x] 6.0a Add `issue_internal_token_transaction()` context manager on `SQLModelAuthRepository` that opens one `Session`, yields a `_SessionIssueTokenTransaction` DTO, and commits/rolls back on exit (kept the existing `refresh_token_transaction` / `internal_token_transaction` shape — additive, not invasive)
- [x] 6.0b `_SessionIssueTokenTransaction` exposes session-bound `create_internal_token` + `record_audit_event` plus an `outbox: OutboxPort` attribute built by an outbox-session-factory callable registered on the repository at composition time; added `AuthIssueTokenTransactionPort` Protocol to `auth_repository.py` and inherited it via `TokenRepositoryPort.issue_internal_token_transaction()`
- [x] 6.0c Added `SQLModelAuthRepository.set_outbox_session_factory(factory)` so the composition root registers the outbox factory after both containers are built — keeps the existing repository constructor signature and avoids forcing the outbox to be built before the auth engine

## 6. Migrate in-tree consumers

- [x] 6.1 `RequestPasswordReset` now opens a single `issue_internal_token_transaction`, writes the token + audit + outbox row through `tx`, and commits once; dropped the `_jobs: JobQueuePort` field; updated `FakeAuthRepository.issue_internal_token_transaction` so unit tests still work
- [x] 6.2 `RequestEmailVerification` migrated the same way
- [x] 6.3 Verified `BootstrapSystemAdmin` does **not** enqueue any email today (only writes the `system:main#admin` relationship tuple via the authz port + a `BootstrapSystemAdmin.execute`-internal audit event). No migration needed.
- [x] 6.4 `build_auth_container` now takes `outbox_session_factory: SessionScopedOutboxFactory` and calls `repo.set_outbox_session_factory(...)` during construction; the `jobs: JobQueuePort` parameter is removed since the request-path consumers no longer need it; `src/main.py`, `src/features/authentication/management.py`, and three test sites (e2e conftest, both atomicity tests, the rate-limit integration tests) updated accordingly
- [x] 6.5 `uv run pytest` → **314 passed** (was 313 before section 5; the new `test_no_relay_in_web.py` accounts for the extra one). `make quality` passes: 19 import-linter contracts kept, mypy clean. Integration tests requiring Docker (`make test-integration`) are deferred to a host with a running PG.

## 7. Contract and integration tests

- [x] 7.1 Added `src/features/outbox/tests/contracts/test_outbox_port_contract.py` covering enqueue+commit, enqueue+rollback, naive-`available_at` rejection, future-`available_at` scheduling, and multi-enqueue-in-one-txn semantics against the in-memory fake (5 tests, all passing). The SQLModel adapter is covered transitively by the integration tests in 7.2.
- [x] 7.2 Added `src/features/outbox/tests/integration/test_relay_dispatch.py` (skipped without Docker): tick-dispatches-pending-row + marks dispatched / clears lock; transient failure increments attempts and advances `available_at`; exhausted attempts flips to `failed`.
- [x] 7.3 Added `src/features/outbox/tests/integration/test_relay_lease.py` (skipped without Docker): two concurrent transactions each run the claim query; assertion is they observe disjoint id sets.
- [x] 7.4 Added `src/features/outbox/tests/unit/test_dispatch_pending.py`: 5 tests covering empty-claim, multi-row dispatch + single mark_dispatched batch, transient retry path, max-attempts → failed, mixed-batch reporting (all passing).
- [x] 7.5 `uv run pytest -q` → 325 passed + 3 pre-existing flaky tests unrelated to this change (caplog-isolation issues that pass on isolated runs). New outbox tests: 11 total. `make ci` deferred to a host with Docker for the integration tier.

## 8. Documentation

- [x] 8.1 Wrote `docs/outbox.md` covering pattern overview, producer contract, consumer contract, relay mechanics, configuration, migration checklist, operational notes (backlog/stuck/failed-row queries + 7-day GC SQL), and out-of-scope items
- [x] 8.2 Updated `docs/architecture.md`: added the `outbox` row to the feature inventory and a "Atomic side effects" row to the cross-feature patterns table pointing at `docs/outbox.md`; also rewrote the "Sending email" row to reference the outbox path
- [x] 8.3 Added the `OutboxSettings` section to `docs/operations.md` env-var tables (5 vars)
- [x] 8.4 Updated `docs/development.md` with `make outbox-retry-failed` row and the "request-path enqueues go through OutboxPort" rule
- [x] 8.5 Added `make outbox-retry-failed` Makefile target backed by `src/features/outbox/management.py` (single SQL UPDATE resetting `status='failed' → 'pending'` with cleared attempts/last_error/locked fields)
- [x] 8.6 Updated `CLAUDE.md`: added the outbox feature row, added the `APP_OUTBOX_*` rows to the env-var table, added the production checklist rule

## 9. Final verification

- [x] 9.1 `make quality` → 19 import-linter contracts kept, 0 broken; mypy clean across 377 source files; ruff lint clean
- [x] 9.2 `make ci` → **311 passed** (unit + e2e), **line coverage 84.99%** (floor 80%), **branch coverage 62.18%** (floor 60%), **integration tier: 17 passed** including 3 new `test_relay_dispatch.py` cases and `test_relay_lease.py`. Ran against local Docker Postgres 16 + Redis 7 after `uv run alembic upgrade head` applied migration `20260515_0012`.
- [x] 9.3 Live dev-stack smoke: started `uv run uvicorn src.main:app` + `uv run python -m src.worker` against the dev Postgres/Redis. `POST /auth/password/forgot` → row landed in `outbox_messages` as `pending` immediately; relay claimed and dispatched it in **2.74 s** (interval=3 s); arq logged the `send_email` job; the console email adapter rendered the actual reset link. End-to-end flow works.
- [x] 9.4 Rollback verification: temporarily added `raise RuntimeError("ROLLBACK SMOKE TEST — DO NOT MERGE")` after `tx.outbox.enqueue(...)` in `RequestPasswordReset.execute`, restarted the API, fired `POST /auth/password/forgot` → got HTTP 500 and **zero** new rows in `outbox_messages` (`recent` count after the call = 0). Reverted the raise; `git diff` confirms only the legit refactor remains.
- [x] 9.5 `openspec validate add-outbox-pattern --strict` → "Change 'add-outbox-pattern' is valid"
