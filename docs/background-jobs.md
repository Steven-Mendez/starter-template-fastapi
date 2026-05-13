# Background Jobs

The `background_jobs` feature owns deferred work. It ships with a port, two
adapters, a handler registry features contribute to, and a worker
entrypoint.

## At A Glance

| Piece | Where |
| --- | --- |
| Port | `src/features/background_jobs/application/ports/job_queue_port.py` — `JobQueuePort.enqueue(name, payload)` and `enqueue_at(name, payload, run_at)` |
| Registry | `src/features/background_jobs/application/registry.py` — `JobHandlerRegistry.register_handler(name, handler)` |
| In-process adapter | `src/features/background_jobs/adapters/outbound/in_process/` |
| `arq` adapter | `src/features/background_jobs/adapters/outbound/arq/` |
| Worker entrypoint | `src/worker.py` (`make worker`) |
| Settings | `src/features/background_jobs/composition/settings.py` (`JobsSettings`) |

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_JOBS_BACKEND` | `in_process` | One of `in_process`, `arq`. **Production refuses `in_process`.** |
| `APP_JOBS_REDIS_URL` | unset | Required when backend is `arq`. Falls back to `APP_AUTH_REDIS_URL` so single-Redis deployments only need one URL. |
| `APP_JOBS_QUEUE_NAME` | `arq:queue` | `arq` queue name. |

## Running The Worker

Locally:

```bash
APP_JOBS_BACKEND=arq APP_JOBS_REDIS_URL=redis://localhost:6379/0 make worker
```

In production, run `python -m worker` as a separate process (sidecar
container, Kubernetes Deployment, systemd unit, etc.). The worker logs the
names of every registered handler at startup so operators can confirm what
it will consume before the first job arrives.

The worker uses the same composition root as the API process so the handler
set must match exactly. If the API enqueues a job name the worker does not
know, the registry raises `UnknownJobError` at startup.

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
   enqueue the job) and `src/worker.py` (so the worker can execute it)
   before `registry.seal()`.

The same handler must be registered in both processes; the registry raises
`UnknownJobError` if the API tries to enqueue a name the worker does not
know about. The sealing step makes drift fail loudly at startup rather than
the first 4 AM enqueue.

## Adapters

### In-process (`InProcessJobQueueAdapter`)

Runs handlers synchronously inline at enqueue time. Used in development,
tests, and CI. Production refuses to start with this backend selected
because losing the web process would lose every queued job.

### arq (`ArqJobQueueAdapter`)

Enqueues onto Redis. The worker process consumes the queue and runs the
handlers. `arq` is async-native and lightweight (~1500 LOC), making it a
natural fit for FastAPI deployments that already use Redis.

The Docker-backed integration test (`src/features/background_jobs/tests/integration/`)
spins up a real Redis container and exercises the full path: enqueue →
worker boot → handler invocation → completion.

## Extending The Feature

- **Schedule jobs ahead of time**: `JobQueuePort.enqueue_at(name, payload, run_at)`
  is supported by the `arq` adapter; the in-process adapter ignores the
  timestamp and runs immediately (intentional, for test determinism).
- **Retry policy**: configure `arq` worker retry behavior in `src/worker.py`.
  The port does not expose per-call retry knobs today; if you need them,
  extend the payload (and the contract test) rather than the port.
- **Different queue backend** (e.g. SQS, dramatiq): implement `JobQueuePort`
  with the new adapter and wire it in `build_jobs_container`. Contract tests
  should pass without modification.
