## Context

The starter today wires `JobQueuePort` as the single mechanism for
deferring work outside the request thread. The web process calls
`port.enqueue(name, payload)` and the active adapter writes the job
somewhere — Redis (`arq`) in production, an inline invocation
(`in_process`) in dev. That works for fire-and-forget work that does
not have to be consistent with a database commit, but every existing
in-tree caller (`RequestPasswordReset`, `RequestEmailVerification`, and
the welcome-email path in `BootstrapSystemAdmin`) does have to be
consistent with one: the use case writes a row (a verification token,
a credential, a relationship tuple) and then enqueues an email that
references it. Today those two writes are independent: the SQL commit
goes to PostgreSQL, the enqueue goes to Redis, nothing crashes-safely
links them.

Two failure modes follow:

1. **Lost email**. SQL `COMMIT` returns, the process dies (or Redis is
   down) before the `arq` push lands. The row exists; the user never
   gets the email.
2. **Phantom email**. With the `in_process` adapter the handler runs
   *inline* — i.e. before the surrounding business transaction
   commits. A subsequent rollback (a unique-constraint violation, a
   panic in the route handler) leaves no row but a delivered email.

A transactional outbox solves both. The use case writes the side-effect
intent into the same SQL transaction as its business state; a separate
process (the worker) polls the table and turns rows into real queue
sends. The DB acts as the consensus layer between "the business
operation happened" and "the side effect must happen". This pattern is
well-documented (Hohpe, Microservices.io's *Transactional Outbox*) and
is the obvious fit for this codebase because the seams are already
right: feature use cases compose outbound ports, the worker is a
first-class process, and SQLModel sessions are already passed in
session-scoped form through the unit-of-work-shaped repositories.

## Goals / Non-Goals

**Goals:**

- Provide a generic `OutboxPort` that any feature can call from inside
  a business transaction to schedule a side effect, with the guarantee
  that the side effect happens **if and only if** the surrounding
  transaction commits.
- Provide at-least-once delivery from the outbox to `JobQueuePort`.
  Consumer handlers stay responsible for idempotency; the outbox does
  not deduplicate on its own.
- Provide a relay loop that runs inside the existing `arq` worker
  process — no new container, no new deployable.
- Keep the existing `JobQueuePort` exactly as-is. The outbox is a
  *producer-side* discipline; the consumer side is unchanged.
- Give operators a production validator that refuses
  `APP_OUTBOX_ENABLED=false` so the wrong default cannot be deployed.
- Migrate the three in-tree consumers to the new path so the starter
  ships the pattern actually in use, not just as a documented option.

**Non-Goals:**

- A domain-event abstraction (`OrderPlaced`, `UserVerified` events
  with typed payloads). The outbox is the *transport*; richer event
  modelling is a consumer concern.
- Cross-aggregate ordering. Rows are claimed in `available_at` order
  but the relay does **not** promise per-aggregate FIFO. If a feature
  needs strict ordering it must partition payloads itself.
- Exactly-once. The relay is at-least-once. Handlers must be
  idempotent — same rule as the bare `JobQueuePort` today.
- A separate `outbox-relay` deployable. One worker process is enough
  for the starter; horizontal scale is achieved by running more
  workers, all of which compete for the same rows via
  `FOR UPDATE SKIP LOCKED`.
- A Kafka / RabbitMQ / SNS adapter on the outbox. The destination is
  always `JobQueuePort.enqueue` in this change.
- Retroactive backfill. There is no migration of "things you might
  have wanted to enqueue before" — the outbox starts empty and the
  in-tree consumers cut over in the same change.

## Decisions

### Decision: One `outbox_messages` table, not a table per feature

We considered a per-feature outbox (each feature owns its own
`<feature>_outbox`) to keep the *outbox ↛ other features* import rule
clean and to let each feature evolve its schema independently. We
rejected it because the **relay** is a single loop scanning a single
index; multiplying tables multiplies index-scan cost on a worker that
already has to wake every few seconds. A single table with
`(status, available_at)` plus a partial index on
`status='pending'` keeps the claim query at one index probe regardless
of how many features produce rows.

Schema:

```text
outbox_messages
  id              uuid pk default gen_random_uuid()
  job_name        text not null
  payload         jsonb not null
  available_at    timestamptz not null default now()
  status          text not null default 'pending'  -- pending|dispatched|failed
  attempts        int not null default 0
  last_error      text null
  locked_at       timestamptz null
  locked_by       text null
  created_at      timestamptz not null default now()
  dispatched_at   timestamptz null

indexes:
  ix_outbox_pending  (available_at) WHERE status = 'pending'
  ix_outbox_created  (created_at)   -- for the documented manual GC query
```

### Decision: Claim with `SELECT ... FOR UPDATE SKIP LOCKED`

Standard PostgreSQL pattern, available since 9.5. Multiple worker
replicas can run the relay concurrently with zero coordination — the
DB itself acts as the work-stealing queue.

Alternative considered: advisory locks per row id. Rejected because
`SKIP LOCKED` is simpler, ships in core, and the relay's claim
batch (default 100) lives entirely inside one short transaction so
the lock window is bounded.

The claim query:

```sql
SELECT id, job_name, payload, attempts
FROM   outbox_messages
WHERE  status = 'pending' AND available_at <= now()
ORDER  BY available_at
LIMIT  :batch_size
FOR    UPDATE SKIP LOCKED;
```

Within the same transaction, we `UPDATE` each claimed row to set
`locked_at = now()` and `locked_by = :worker_id` so an operator can
see *which* worker has a row mid-flight, then commit. After dispatch
we open a second short transaction to mark each row `dispatched` (on
success) or to increment `attempts` and clear the lock (on failure).

### Decision: `OutboxPort.enqueue(...)` is synchronous and session-scoped

The port is a method on a session-scoped adapter — same pattern as
`SessionSQLModelAuthorizationAdapter`. The session-scoped adapter is
constructed inside a write transaction owned by the feature's
repository and bound to that session. The atomic guarantee is therefore
automatic: the row goes in the same `INSERT` batch as the rest of the
transaction and commits or rolls back with it.

### Decision: Introduce a `write_transaction()` context manager on `SQLModelAuthRepository`

The authentication feature today does **not** expose a use-case-level
unit of work: each repository method (`create_internal_token`,
`record_audit_event`, …) opens its own session in `_write_session_scope`
and commits standalone, so a consumer like `RequestPasswordReset`
performs three independent commits. That shape is incompatible with the
outbox's atomic contract — there is no caller-owned transaction the
outbox row can hitch onto.

We add a new `write_transaction()` context manager on
`SQLModelAuthRepository` that opens one `Session` and yields a small
`AuthWriteTransaction` DTO exposing the *same* operations
(`create_internal_token`, `record_audit_event`, `upsert_credential`,
`record_used_token`, …) plus an `.outbox` attribute already bound to
that session. `RequestPasswordReset`,
`RequestEmailVerification`, `ConfirmPasswordReset`,
`ConfirmEmailVerification`, and `RegisterUser` move from calling the
old methods directly to `with self._repository.write_transaction() as
tx: tx.create_internal_token(...); tx.outbox.enqueue(...)`. One commit,
one rollback, atomic by construction.

The pre-existing standalone methods stay — read paths and use cases
that do not need atomicity (`LogoutUser`, `RotateRefreshToken`) keep
using them. The new context is additive.

Alternative considered: a generic `UnitOfWorkPort` injected per
feature. Rejected because the starter has not adopted a generic UoW
elsewhere, the auth feature is the only one with the multi-write
problem today, and the repository already owns the engine and session
lifecycle so the new method has zero new moving parts.

Signature:

```python
class OutboxPort(Protocol):
    def enqueue(
        self,
        *,
        job_name: str,
        payload: dict[str, Any],
        available_at: datetime | None = None,
    ) -> None: ...
```

Alternative considered: an *engine-scoped* `OutboxPort` that opens its
own session. Rejected because that loses the atomic guarantee — the
whole point of the pattern.

### Decision: The relay is an `arq` cron job, not a standalone loop

We considered a long-lived `asyncio.Task` started by the worker
entrypoint. Rejected because the existing worker already has a
scheduler abstraction (`cron_jobs` in arq), it's the natural place to
put a recurring task, and it gives us free observability via the same
job logs operators already monitor.

The relay registers as `arq.cron("outbox-relay", run_at_startup=True,
seconds=APP_OUTBOX_RELAY_INTERVAL_SECONDS)` — wakes every 5 s by
default, claims up to `APP_OUTBOX_CLAIM_BATCH_SIZE` rows, dispatches
them, sleeps. The web process never registers this cron and never runs
the loop.

### Decision: Backoff on dispatch failure is fixed-delay, not exponential

We considered exponential backoff (`available_at += 2 ** attempts`).
Rejected for the starter because:

1. The relay's destination is `JobQueuePort.enqueue`, which is a
   local Redis push. The realistic failure modes are "Redis down for
   a few seconds" or "Redis down for a long time" — both of which a
   30-second retry handles correctly. Exponential delays do not help
   the second case (it would just defer the next attempt further)
   and the first case wants prompt retries.
2. Exponential delays add a column and a code path consumers will
   need to understand. The starter's job is to be obvious.

Behaviour: `attempts += 1`, `available_at = now() + 30 s`,
`last_error = repr(exception)`. Once `attempts >= APP_OUTBOX_MAX_ATTEMPTS`
(default 8) the row flips to `status='failed'` and stays out of the
claim query. An operator query (`SELECT * FROM outbox_messages WHERE
status='failed'`) surfaces them; a `make outbox-retry-failed` Makefile
target re-arms them by resetting `status` and `attempts`.

### Decision: Production validator refuses `APP_OUTBOX_ENABLED=false`

Same shape as the `email_backend != 'console'` rule. Operators must
explicitly enable the outbox in production. The relay starting in the
worker depends on this flag, and the consumer use cases call
`OutboxPort.enqueue` unconditionally — so a deployment with the flag
off would silently stop sending emails. The validator surfaces that
combination as a startup failure instead.

### Decision: Keep `JobQueuePort.enqueue` available for non-transactional callers

We considered locking the codebase down to "all enqueues go through
the outbox". Rejected because there are valid non-transactional
callers: the relay itself is one. Cron-like scheduled work that does
not co-write a business row is another. Instead, an Import Linter
rule forbids the *authentication* feature from importing the
background-jobs adapters directly — that's where the bug lived — and
the migration steps in `tasks.md` flip every existing in-tree caller
explicitly.

### Decision: The in-memory fake `OutboxPort` runs handlers synchronously, like the in-process `JobQueuePort`

Test ergonomics dominate here. Unit and e2e tests already use the
in-process job queue, which runs handlers inline; that lets a single
test assert "I called `RequestPasswordReset`, an email was sent". If
the fake outbox required tests to also drive the relay manually,
every existing test that relies on this would grow a new step. The
fake therefore dispatches inline at `enqueue` time *after* the test's
explicit commit — i.e. the fake takes a `commit_hook` that
`UnitOfWork.commit` calls, and only then drains. Tests that exercise
relay semantics (failure / retry / claim) use the SQLModel adapter
against testcontainers PostgreSQL.

## Risks / Trade-offs

- **Risk**: Relay lag during a worker outage means side effects pile
  up but do not deliver. → **Mitigation**: The web process keeps
  writing rows — nothing is lost. The `relay_interval_seconds` knob
  lets operators tune for their SLO, and a Grafana query on
  `count(status='pending' AND available_at < now() - interval '1
  minute')` makes the backlog observable.
- **Risk**: A pathological handler that always fails consumes the
  claim batch repeatedly. → **Mitigation**: `max_attempts` caps the
  retry budget per row; a failed row stops competing for budget once
  it crosses the threshold.
- **Risk**: A long-running consumer transaction holds the outbox row
  insert open and delays the relay's view. → **Mitigation**: Inherent
  to MVCC and acceptable — the row only becomes visible to the relay
  *after* commit, which is the desired semantic.
- **Risk**: Adding a new feature outbound port (`OutboxPort`) to the
  authentication use cases is a constructor-signature change.
  → **Mitigation**: Authentication's tests already build the
  container; the swap is a one-line constructor edit. The migration
  tasks call this out per use case.
- **Risk**: `outbox_messages` grows without bound if nobody runs the
  cleanup query. → **Mitigation**: Documented in `docs/outbox.md`,
  flagged as a follow-up — not solved in this change because the
  retention policy is operator-specific.
- **Risk**: The `outbox ↛ other features` rule plus
  `authentication ↛ background_jobs.adapters` could be over-strict if
  a future feature legitimately wants to enqueue without a
  transaction. → **Mitigation**: Such features compose
  `JobQueuePort` directly from their own container — the rule only
  blocks `authentication`'s use cases from regressing.
- **Trade-off**: One DB write per side effect adds row cost.
  → **Mitigation**: This is the standard cost of the pattern;
  consumer features that need throughput well above the relay's
  rate should partition (multiple workers) or use a dedicated
  queue path (composed directly off `JobQueuePort`). The starter's
  workload is dominated by auth flows, where this is negligible.
- **Trade-off**: Operators must now run the worker even for
  dev/test if they want emails to actually leave the box. The
  `in_process` job-queue path still works inline because the
  in-memory fake outbox dispatches on commit — so the "no worker
  needed for dev" experience is preserved.
