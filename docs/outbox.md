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

The `outbox` attribute on the transaction is a session-scoped
`OutboxPort` already bound to the surrounding SQL session. You
never call `commit()` on it; the repository's context manager owns
the commit. That's what gives the pattern its atomic guarantee:

> A side effect is dispatched **if and only if** the surrounding
> business transaction commits.

`available_at` is optional. When `None`, the row is eligible
immediately; when set, it must be timezone-aware and the relay will
not claim it until `now() >= available_at`.

## Consumer contract

Consumers are unchanged from today: they are handlers registered
against `JobHandlerRegistry`, called from `JobQueuePort.enqueue`.
The relay simply re-emits the outbox payload as if a normal producer
had enqueued it.

**Handlers MUST be idempotent.** The relay is at-least-once: a row
can be dispatched more than once if a worker crashes between
`JobQueuePort.enqueue` and the row's `mark_dispatched` write. The
typical handler — "load this user, send this email" — is naturally
idempotent if the underlying side effect tolerates re-execution
(email providers are normally fine with this because they
deduplicate on `Message-ID`).

## How the relay works

The worker (`src/worker.py`) registers `DispatchPending` as an arq
cron job that fires every `APP_OUTBOX_RELAY_INTERVAL_SECONDS`. Each
tick:

1. Opens a short transaction, runs
   `SELECT ... FROM outbox_messages WHERE status='pending' AND
   available_at <= now() ORDER BY available_at LIMIT :batch
   FOR UPDATE SKIP LOCKED`, and stamps `locked_at` / `locked_by`
   on each row. The lock window is bounded by the size of the
   batch (default 100), not by the dispatch duration.
2. For each claimed row, calls `JobQueuePort.enqueue(name, payload)`.
3. On success, marks the row `dispatched` and records `dispatched_at`.
4. On failure, increments `attempts`, records `last_error`,
   advances `available_at` by 30 s, and leaves the row `pending`.
   Once `attempts >= APP_OUTBOX_MAX_ATTEMPTS` (default 8) the row
   flips to `failed` and stops competing for relay budget.

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
   template: hold the session and the outbox-session adapter
   built by the repository's registered factory.
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
- **Retention**: Dispatched rows accumulate. The starter ships no
  GC job; run a periodic cleanup if your write volume warrants:
  ```sql
  DELETE FROM outbox_messages
  WHERE status = 'dispatched'
    AND dispatched_at < now() - interval '7 days';
  ```

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
  consumers are the user's responsibility.
