# Background Jobs

The `background_jobs` feature owns deferred work. It ships with a port,
the `in_process` adapter, a handler registry features contribute to, and
a runtime-agnostic worker composition-root scaffold.

> **No production job runtime yet.** The `arq` adapter and its worker
> runtime were removed in ROADMAP ETAPA I step 5. The production job
> runtime (AWS SQS + a Lambda worker) arrives at a later roadmap step
> (steps 26-27). `in_process` is the only shipped adapter, and the
> production validator refuses it — production with deferred work is
> intentionally not bootable until the AWS runtime lands.

## At A Glance

| Piece | Where |
| --- | --- |
| Port | `src/features/background_jobs/application/ports/job_queue_port.py` — `JobQueuePort.enqueue(name, payload)` and `enqueue_at(name, payload, run_at)` |
| Registry | `src/features/background_jobs/application/registry.py` — `JobHandlerRegistry.register_handler(name, handler)` |
| In-process adapter | `src/features/background_jobs/adapters/outbound/in_process/` |
| Cron descriptor | `src/features/background_jobs/application/cron.py` — runtime-agnostic `CronSpec` |
| Worker scaffold | `src/worker.py` (`make worker`) |
| Settings | `src/features/background_jobs/composition/settings.py` (`JobsSettings`) |

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_JOBS_BACKEND` | `in_process` | Only accepted value is `in_process`. **Production refuses it** — there is no production job backend until AWS SQS is added at a later roadmap step. |

## Running The Worker

```bash
make worker
```

`src/worker.py` is a runtime-agnostic composition-root + handler/cron
registry scaffold. It builds the same composition root the API process
uses (so composition errors surface loudly), logs the names of every
registered handler and collected cron descriptor, then exits non-zero
with a clear message: no job runtime is wired. The production job
runtime (AWS SQS + a Lambda worker) arrives at a later roadmap step,
which re-binds the preserved registry + cron descriptors to a real
scheduler.

The scaffold uses the same composition root as the API process so the
handler set matches exactly. If the API enqueues a job name that is not
registered, the registry raises `UnknownJobError` at startup.

## How To Enqueue Work

Take `JobQueuePort` as a constructor dependency in your use case:

```python
class RequestPasswordReset:
    def __init__(self, jobs: JobQueuePort) -> None:
        self._jobs = jobs

    def execute(self, *, email: str, token: str) -> None:
        self._jobs.enqueue(
            "send_email",
            payload={
                "to": email,
                "template_name": "password_reset",
                "context": {"token": token},
            },
        )
```

Payloads are plain dicts — keep them JSON-serializable so any backend can
round-trip them.

## Adding A Handler

1. Write a sync callable in your feature's `application/` or `composition/`
   package:

   ```python
   def send_welcome_email(payload: dict[str, Any]) -> None:
       ...
   ```

2. Expose a `register_<name>_handler(registry, ...)` helper from your
   feature's composition module. The helper takes any dependencies the
   handler needs and closes over them when registering:

   ```python
   def register_welcome_email_handler(
       registry: JobHandlerRegistry,
       email_port: EmailPort,
   ) -> None:
       def handler(payload: dict[str, Any]) -> None:
           email_port.send(
               to=payload["to"],
               template_name="welcome",
               context=payload["context"],
           )

       registry.register_handler("send_welcome_email", handler)
   ```

3. Call that helper from **both** `src/main.py` (so the API process can
   enqueue the job) and `src/worker.py` (so the future job runtime can
   execute it) before `registry.seal()`.

The same handler must be registered in both composition roots; the
registry raises `UnknownJobError` if the API tries to enqueue a name
that is not registered. The sealing step makes drift fail loudly at
startup rather than the first 4 AM enqueue.

## Adapters

### In-process (`InProcessJobQueueAdapter`)

Runs handlers synchronously inline at enqueue time. Used in development,
tests, and CI — it is the only shipped adapter. Production refuses to
start with this backend selected because losing the web process would
lose every queued job, and there is no other backend until the AWS SQS
adapter is added at a later roadmap step.

## Cron Descriptors

Recurring work (the outbox relay/prune, the auth token purge) is
declared as runtime-agnostic `CronSpec` descriptors
(`src/features/background_jobs/application/cron.py`): a `name`, an
already-snapped `interval_seconds`, a `run_at_startup` flag, and a
zero-arg synchronous `callable`. `src/worker.py` collects them so the
schedules are declared once and unit-tested without a scheduler. The
future job runtime binds them to a real scheduler.

## Extending The Feature

- **Schedule jobs ahead of time**: `JobQueuePort.enqueue_at(name, payload, run_at)`
  is part of the port contract. The in-process adapter raises
  `NotImplementedError` (no scheduler); scheduled execution requires the
  production job runtime, added at a later roadmap step.
- **Production job backend**: the `aws_sqs` adapter and a Lambda worker
  arrive at a later roadmap step (steps 26-27). Implementing it means
  adding a `JobQueuePort` adapter and wiring it in `build_jobs_container`;
  the contract tests should pass without modification.
