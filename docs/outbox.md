# Transactional Outbox

This feature gives the starter a single, opinionated way to ship a
side effect from a request handler to a background worker **without
losing or duplicating it across a process crash**. It solves the
"SQL commit succeeded but the Redis push failed" class of bugs that
the unguarded `JobQueuePort.enqueue` path is vulnerable to.

## When to use it

Use the outbox whenever a use case both:

1. Writes business state to PostgreSQL, **and**
2. Needs to trigger a side effect (an email, a webhook, an event
   broadcast) when that state successfully commits.

If you don't have a database write to anchor the side effect to —
say, a periodic cleanup job — keep using `JobQueuePort` directly.

## Producer contract

```python
with self._repository.issue_internal_token_transaction() as tx:
    tx.create_internal_token(...)
    tx.record_audit_event(...)
    tx.outbox.enqueue(
        job_name="send_email",
        payload={"to": "...", "template_name": "...", "context": {...}},
    )
# One COMMIT — token row, audit event, and outbox row become visible
# together. A rollback drops all three.
```

The `outbox` attribute on the transaction is a session-scoped writer
already bound to the surrounding SQL session. You never call
`commit()` on it; the repository's context manager owns the commit.
That's what gives the pattern its atomic guarantee:

> A side effect is dispatched **if and only if** the surrounding
> business transaction commits.

`available_at` is optional. When `None`, the row is eligible
immediately; when set, it must be timezone-aware and the relay will
not claim it until `now() >= available_at`.

### Wiring producers through the unit-of-work port

Producer composition takes an `OutboxUnitOfWorkPort`, not a session-
typed factory — the port keeps SQLModel out of the producer's wiring
surface so a future Mongo-backed outbox can satisfy the same seam.

```python
# features/outbox/application/ports/outbox_uow_port.py
class OutboxUnitOfWorkPort(Protocol):
    def transaction(self) -> AbstractContextManager[OutboxWriter]: ...

class OutboxWriter(Protocol):
    def enqueue(self, *, job_name, payload, available_at=None): ...
```

```python
# main.py — produce the port from the outbox container and hand it
# to the producer composition. Note the absence of ``sqlmodel.Session``
# in the producer's signature.
outbox = build_outbox_container(settings, engine=engine, job_queue=jobs.port)
auth = build_auth_container(
    settings=app_settings,
    users=users.user_repository,
    outbox_uow=outbox.unit_of_work,
    repository=repository,
)
```

The SQLModel implementation (`SQLModelOutboxUnitOfWork`) owns a
`sessionmaker` internally and exposes the active session on its
writer so SQLModel-aware producer adapters (the auth repository) can
attach their token + audit writes to the same transaction. Producer
*composition* depends only on the port; the Session never appears in
the wiring layer.

## Consumer contract

Consumers are handlers registered against `JobHandlerRegistry`, called
from `JobQueuePort.enqueue`. The relay re-emits the outbox payload as
if a normal producer had enqueued it, plus one reserved key the relay
injects on every dispatch (see "Reserved payload keys" below).

**Handlers MUST be idempotent on `__outbox_message_id`.** The relay
is at-least-once: a row can be dispatched more than once if a worker
crashes between `JobQueuePort.enqueue` and the per-row
`mark_delivered` commit. The starter ships a small dedup table —
`processed_outbox_messages` — keyed on `OutboxMessage.id`. Handlers
insert into that table inside their own transaction; a duplicate-PK
collision means the message was already processed and the handler
MUST short-circuit to `Ok`. The bundled `send_email` handler does
this for you when you wire it through the outbox composition
(`build_handler_dedupe(engine)`).

### Row-state machine

Each row in `outbox_messages` moves through the strict state machine:

```
pending --(enqueue + commit)--> delivered
pending --(attempts >= max)----> failed
```

The success-state column is `delivered_at`; the failure-state column
is `failed_at`. The relay flips a row to `delivered` only after
`JobQueuePort.enqueue` returns successfully and the row's
transaction commits — a crash between the enqueue and the commit
leaves the row `pending` for the next tick to re-claim (which is
safe because handlers dedup on `__outbox_message_id`).

### Reserved payload keys

The relay owns the `__*` prefix inside the job payload. Non-reserved
keys are the producer's original payload; the relay never modifies
them. Handlers that re-enqueue a payload (manual replay, redrive
tooling) MUST preserve every `__*` key they received — including
keys they do not understand — so future cluster changes can add
reserved keys without breaking older deployments.

| Key | Type / shape | Purpose |
|---|---|---|
| `__outbox_message_id` | `str` (UUID) | Handler-side dedup token |
| `__trace` | `{"traceparent": str, "tracestate"?: str}` (W3C) | Trace context propagation (sibling change `propagate-trace-context-through-jobs`) |

## How the relay works

The worker (`src/worker.py`) registers `DispatchPending` as an arq
cron job that fires every `APP_OUTBOX_RELAY_INTERVAL_SECONDS`. Each
tick:

1. Opens a short transaction, runs
   `SELECT ... FROM outbox_messages WHERE status='pending' AND
   available_at <= now() ORDER BY available_at, id LIMIT :batch
   FOR UPDATE SKIP LOCKED`, and stamps `locked_at` / `locked_by`
   on each row. The lock window is bounded by the size of the
   batch (default 100), not by the dispatch duration. The
   `(available_at, id)` partial index supports the claim path; the
   `id` tiebreaker gives SKIP LOCKED a deterministic scan order.
2. For each claimed row, opens a per-row writer transaction,
   injects `__outbox_message_id` into the payload (and `__trace`
   from `outbox_messages.trace_context` when present, so handler
   spans become children of the originating request's trace), calls
   `JobQueuePort.enqueue(name, payload)`, and marks the row
   `delivered` in the same transaction. A crash between the enqueue
   and the commit leaves the row `pending` for the next tick to
   re-claim (handlers dedup on `__outbox_message_id`).
3. On failure, increments `attempts`, records `last_error`, and
   advances `available_at` with exponential backoff:
   `min(retry_base * 2^(attempts-1), retry_max)`. Defaults are
   `retry_base=30s` and `retry_max=900s`. Once
   `attempts >= APP_OUTBOX_MAX_ATTEMPTS` (default 8) the row flips
   to `failed`, records `failed_at`, and stops competing for relay
   budget.

`FOR UPDATE SKIP LOCKED` is the standard PostgreSQL idiom that lets
multiple worker replicas share one outbox table with zero
coordination — each replica observes only rows the others have not
claimed yet.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `APP_OUTBOX_ENABLED` | `false` | Master switch. Production refuses `false`. |
| `APP_OUTBOX_RELAY_INTERVAL_SECONDS` | `5.0` | Snap-to-divisor-of-60 cron cadence. |
| `APP_OUTBOX_CLAIM_BATCH_SIZE` | `100` | Max rows per claim transaction. |
| `APP_OUTBOX_MAX_ATTEMPTS` | `8` | Per-row retry budget before flipping to `failed`. |
| `APP_OUTBOX_WORKER_ID` | `<hostname>:<pid>` | Stamped onto `locked_by` for operator visibility. |
| `APP_OUTBOX_RETRY_BASE_SECONDS` | `30.0` | Base delay for the exponential retry backoff. |
| `APP_OUTBOX_RETRY_MAX_SECONDS` | `900.0` | Cap on the retry backoff. |
| `APP_OUTBOX_RETENTION_DELIVERED_DAYS` | `7` | Delivered rows older than this are pruned by the hourly cron. |
| `APP_OUTBOX_RETENTION_FAILED_DAYS` | `30` | Failed rows older than this are pruned by the hourly cron. |
| `APP_OUTBOX_PRUNE_BATCH_SIZE` | `1000` | Max rows the prune cron deletes per transaction. The use case loops internally until the eligible set is empty. |

The web process does NOT need any of these set — the request-path
producers always write to the outbox regardless. The relay only
runs in the worker process, gated on `APP_OUTBOX_ENABLED=true`.

## Migrating a new consumer

To convert a use case that calls `JobQueuePort.enqueue` directly
into an outbox-backed flow:

1. Identify the surrounding SQL write. If the use case does not
   already participate in a single transaction, refactor it to
   open one — pattern: add a `<name>_transaction()` context
   manager on the repository.
2. The yielded transaction DTO needs to expose an `outbox`
   attribute. Follow `_SessionIssueTokenTransaction` as a
   template: hold the session and the writer yielded by the
   repository's `OutboxUnitOfWorkPort.transaction()` context.
3. Replace `self._jobs.enqueue(...)` with
   `tx.outbox.enqueue(job_name=..., payload=...)`.
4. Drop the `_jobs: JobQueuePort` field from the use case if it
   no longer needs to enqueue outside the transaction.
5. The `send_email` handler (or your own) is unchanged.

## Operational notes

- **Backlog**: A growing `count(status='pending' AND available_at
  < now() - interval '1 minute')` indicates the relay is falling
  behind. Either the worker is down or the dispatch cadence is too
  slow for the producer rate. Tune `APP_OUTBOX_RELAY_INTERVAL_SECONDS`
  / `APP_OUTBOX_CLAIM_BATCH_SIZE` or scale workers.
- **Stuck rows**: A row with non-null `locked_at` older than a few
  minutes indicates a worker crashed mid-dispatch. The next relay
  tick on a healthy worker will re-claim it because the claim
  query selects on `status`, not on `locked_at`.
- **Failed rows**: `SELECT * FROM outbox_messages WHERE
  status='failed'` shows everything that exceeded the retry
  budget. To re-arm them, run `make outbox-retry-failed` (or
  manually: `UPDATE outbox_messages SET status='pending',
  attempts=0, available_at=now() WHERE status='failed';`).
- **Retention**: The worker schedules an hourly cron (`outbox-prune`)
  that drains terminal-state rows and stale dedup marks via the
  `PruneOutbox` use case. Defaults:
  - `delivered` rows older than `APP_OUTBOX_RETENTION_DELIVERED_DAYS`
    (default 7 days) are deleted. These are best-effort audit trail
    and are pruned aggressively.
  - `failed` rows older than `APP_OUTBOX_RETENTION_FAILED_DAYS`
    (default 30 days) are deleted. Failed rows are operator-actionable
    evidence of dead-lettered work and are kept longer.
  - `processed_outbox_messages` rows older than
    `2 × APP_OUTBOX_RETRY_MAX_SECONDS` are deleted. The dedup window
    is pegged to the retry budget rather than a separate knob: by the
    time we delete a mark, the corresponding outbox row has already
    reached a terminal state.

  Each delete runs in its own short transaction bounded by
  `APP_OUTBOX_PRUNE_BATCH_SIZE` (default 1000); the use case loops
  internally until the eligible set is empty, keeping each transaction
  autovacuum and replica friendly. For a one-shot manual sweep (e.g.
  before a maintenance window), run `make outbox-prune` — it invokes
  the same use case as the cron, using the same settings.

## Not in scope

- A typed domain-event abstraction (event payloads stay as the
  job's existing `dict[str, Any]`).
- Per-aggregate ordering. Rows are dispatched roughly in
  `available_at` order but two side effects from the same
  aggregate can be picked up by different workers — order across
  the boundary is not guaranteed.
- A Kafka / RabbitMQ / SNS adapter. The destination is always
  `JobQueuePort`. Swap the queue's adapter if you need a
  different transport.
- Exactly-once delivery. The relay is at-least-once; idempotent
  consumers (dedup on `__outbox_message_id`) are the contract.
