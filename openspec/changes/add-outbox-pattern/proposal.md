## Why

Today, when a use case both persists state and enqueues background work in
the same request, the two writes can disagree. `RequestPasswordReset`,
`RequestEmailVerification`, and the `BootstrapSystemAdmin` flow each
commit a row to PostgreSQL **and** push a `send_email` job onto Redis via
`JobQueuePort.enqueue(...)`. The DB commit and the Redis push are
independent network calls: if Redis is unreachable (or the worker has
crashed, or the process dies between the two calls) the database row
sticks but the email is never sent. The reverse is also possible — the
in-process adapter runs handlers inline before the surrounding DB
transaction has committed, so a rolled-back transaction can still send
an email referencing a user that no longer exists.

Operators picking up this template will eventually hit this exact bug.
A transactional outbox is the standard fix: write the side-effect
intent into the same database transaction as the business state, then
let a separate relay deliver it to the queue. The starter has all the
right seams to ship this generically — a `JobQueuePort`, per-feature
unit-of-work-shaped repositories, a worker entrypoint, and a settings
production validator — so making it a first-class feature now keeps
every future consumer correct by default.

## What Changes

- Add a new `outbox` feature under `src/features/outbox/` that owns the
  `outbox_messages` table, the `OutboxPort` (called from inside a
  business transaction to record a pending side effect), and the
  `OutboxRelay` (called from the worker to claim pending rows and
  dispatch them through `JobQueuePort`).
- Introduce one PostgreSQL table `outbox_messages` with columns
  `id` (uuid pk), `job_name` (text), `payload` (jsonb), `available_at`
  (timestamptz, default `now()`), `status` (text, one of
  `pending|dispatched|failed`), `attempts` (int), `last_error` (text
  nullable), `locked_at`/`locked_by` (timestamptz/text nullable for
  worker leasing), `created_at`, `dispatched_at`. Indexed on
  `(status, available_at)` for the relay's claim query, with a partial
  index `WHERE status = 'pending'` to keep claim scans cheap once the
  table grows.
- Add `OutboxPort.enqueue(job_name, payload, *, available_at=None)` —
  the inbound contract callers use. The SQLModel adapter writes a row
  using whatever session the caller is already in, so the row commits
  atomically with the surrounding business writes.
- Add `OutboxRelay` as an `arq` cron-style job (and a `make outbox-relay`
  one-shot dispatch entrypoint for tests) that claims up to `N` pending
  rows with `SELECT ... FOR UPDATE SKIP LOCKED LIMIT N`, calls
  `JobQueuePort.enqueue(...)` for each, and either marks them
  `dispatched` on success or increments `attempts` + records
  `last_error` on failure. Permanently failed rows after
  `APP_OUTBOX_MAX_ATTEMPTS` are flipped to `status='failed'` and stop
  consuming claim budget.
- Migrate the two existing in-tree consumers — the authentication
  feature's password-reset and email-verify use cases, and the
  authorization feature's `BootstrapSystemAdmin` — from calling
  `JobQueuePort.enqueue` directly to calling `OutboxPort.enqueue`. The
  `send_email` handler itself does not change; only the path that
  produces the request changes.
- Extend the worker (`src/worker.py`) to schedule the relay on a fixed
  interval (default 5 s) when `APP_OUTBOX_ENABLED=true`. The web
  process never runs the relay loop; it only writes outbox rows.
- Add `OutboxSettings` with fields `enabled` (bool, default `false`),
  `relay_interval_seconds` (default `5.0`), `claim_batch_size` (default
  `100`), `max_attempts` (default `8`), `worker_id` (string identifying
  the relay instance). `validate_production` requires
  `enabled=true` so production deployments cannot regress to the
  fire-and-forget enqueue path.
- Add an Alembic migration for the `outbox_messages` table.
- Add a contract suite under `src/features/outbox/tests/contracts/` that
  runs against an in-memory fake `OutboxPort` (for fast unit/e2e tests)
  and against the SQLModel adapter (for the integration tier).
- Update `docs/architecture.md`, `docs/operations.md`, `CLAUDE.md`, and
  add a `docs/outbox.md` deep-dive covering: the at-least-once delivery
  contract, idempotency requirements on consumer handlers, the claim
  lease semantics, and a checklist for migrating a use case off the
  direct `JobQueuePort.enqueue` path.

This change does **not** introduce a separate process. The relay is an
`arq` recurring job that piggybacks on the existing worker — operators
already need the worker for production, so the operational footprint
stays unchanged.

## Capabilities

### New Capabilities

- `outbox`: codifies the `OutboxPort` and `OutboxRelay` contracts —
  atomic enqueue from inside a business transaction, at-least-once
  delivery semantics, the claim/lease state machine
  (`pending → dispatched | failed`), retry behaviour, and the
  per-backend rules for the SQLModel adapter and the in-memory fake.
  Also codifies the production rule that consumers of `JobQueuePort`
  inside a request path must go through `OutboxPort` instead of calling
  `JobQueuePort.enqueue` directly.

### Modified Capabilities

<!-- None: outbox is a new capability. The authentication and authorization
specs already exist under openspec/specs/, but the changes there are
implementation-level (swap one outbound port call for another) and do
not move spec-level requirements. -->

## Impact

- **Code (new)**:
  - `src/features/outbox/domain/{message.py,status.py}`
  - `src/features/outbox/application/ports/outbox_port.py`
  - `src/features/outbox/application/ports/outbound/outbox_repository_port.py`
  - `src/features/outbox/application/use_cases/dispatch_pending.py`
  - `src/features/outbox/adapters/outbound/sqlmodel/{models.py,adapter.py,repository.py}`
  - `src/features/outbox/composition/{container.py,wiring.py,settings.py,worker.py}`
  - `src/features/outbox/tests/{unit,contracts,fakes,integration}/...`
  - `alembic/versions/<rev>_outbox_messages.py`
  - `docs/outbox.md`
- **Code (modified)**:
  - `src/features/authentication/application/use_cases/auth/{request_password_reset.py,request_email_verification.py}`
    — swap `jobs.enqueue("send_email", ...)` for
    `outbox.enqueue("send_email", ...)`. Use case constructor takes
    `OutboxPort` instead of `JobQueuePort`.
  - `src/features/authentication/composition/container.py` — accept and
    pass `OutboxPort` instead of `JobQueuePort` to the relevant use
    cases.
  - `src/features/authorization/application/use_cases/bootstrap_system_admin.py`
    — same swap, if it enqueues a welcome email.
  - `src/main.py` — build the `OutboxContainer` between
    `email`/`jobs` and `authentication`; pass the port into the auth
    container. No relay loop in the web process.
  - `src/worker.py` — schedule the relay cron job when
    `APP_OUTBOX_ENABLED=true`.
  - `src/platform/config/settings.py` — new `APP_OUTBOX_*` env vars and
    a `settings.outbox` projection.
  - `pyproject.toml` — Import Linter contracts: `outbox ↛ other features`
    (same pattern as `email`/`background_jobs`/`file_storage`), and an
    explicit `authentication ↛ background_jobs.adapters` rule so the
    auth feature cannot accidentally bypass the outbox.
- **Configuration**: new env vars `APP_OUTBOX_ENABLED` (bool, default
  `false`), `APP_OUTBOX_RELAY_INTERVAL_SECONDS` (float, default `5.0`),
  `APP_OUTBOX_CLAIM_BATCH_SIZE` (int, default `100`),
  `APP_OUTBOX_MAX_ATTEMPTS` (int, default `8`),
  `APP_OUTBOX_WORKER_ID` (string, default a stable hash of hostname +
  pid).
- **Dependencies**: none new. The relay uses the existing
  SQLAlchemy/SQLModel session, the existing `arq` worker, and the
  existing `JobQueuePort`.
- **Database**: one new table (`outbox_messages`) plus its indexes.
  Expected steady-state row count is "messages in flight"; a periodic
  `DELETE WHERE status='dispatched' AND dispatched_at < now() - interval
  '7 days'` is documented but not implemented as a job in this change.
- **Operational footprint**: no new process. Operators must run the
  existing `arq` worker; the relay registers itself there.
- **Docs**: `docs/outbox.md` (new), `docs/architecture.md` (add the
  outbox to the feature inventory + dependency graph),
  `docs/operations.md` (env-var table), `CLAUDE.md` (feature inventory,
  cross-feature pattern row, production checklist row).
- **Out of scope**: a generic event-bus / domain-event layer that
  publishes typed events from domain objects (the outbox is the
  *transport*, not the *event model*); ordering guarantees across
  messages (the relay is best-effort FIFO on `available_at` but does
  not promise per-aggregate ordering); a separate `outbox-relay`
  process or container; outbox-to-Kafka/RabbitMQ adapters; tombstoning
  / GC of dispatched rows beyond a documented manual query.
