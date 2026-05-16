# Tasks — remove-arq-adapter (ROADMAP ETAPA I step 5, sub-step 5a)

## 1. Delete the arq adapter package

- [x] Delete `src/features/background_jobs/adapters/outbound/arq/adapter.py`
- [x] Delete `src/features/background_jobs/adapters/outbound/arq/worker.py`
- [x] Delete `src/features/background_jobs/adapters/outbound/arq/__init__.py`
- [x] Delete the now-empty
      `src/features/background_jobs/adapters/outbound/arq/` directory
      (including any `__pycache__`)

## 2. Runtime-agnostic cron descriptor

- [x] Add a `CronSpec` dataclass (`@dataclass(frozen=True, slots=True)`:
      `name: str`, `interval_seconds: int`, `run_at_startup: bool`,
      `callable: Callable[[], None]`) under
      `src/features/background_jobs/` — preferred path
      `application/cron.py` (application layer, no framework imports).
      **Verify with `make lint-arch`** that the `outbox` and
      `authentication` `composition/worker.py` modules importing this
      symbol does not violate an Import Linter contract; if it does,
      relocate `CronSpec` to a platform-neutral location the contracts
      allow (implementer latitude — resolve against `make lint-arch`,
      do not guess)
- [x] Rewrite `src/features/outbox/composition/worker.py`:
      `build_relay_cron_jobs` → `build_relay_cron_specs(container) ->
      Sequence[CronSpec]`. Carry forward verbatim: `_snap_to_divisor`,
      the `if not container.settings.enabled: return []` gate, the
      `outbox-relay` (interval, `run_at_startup=True`) and
      `outbox-prune` (hourly) entries, all log lines. Replace only the
      `arq.cron.cron(...)` wrapping with `CronSpec(...)`; the relay/prune
      `callable`s become plain zero-arg syncs that call
      `container.dispatch_pending.execute()` /
      `container.prune_outbox.execute(...)` (drop the `ctx` param). Remove
      `from arq.cron import CronJob, cron`
- [x] Rewrite `src/features/authentication/composition/worker.py`:
      `build_auth_maintenance_cron_jobs` →
      `build_auth_maintenance_cron_specs(...) -> Sequence[CronSpec]`.
      Carry forward verbatim: `_snap_to_divisor`, the
      `if interval_minutes <= 0: return []` kill-switch gate, the
      `auth-purge-tokens` entry, all log lines. Replace `cron(...)` with
      `CronSpec(...)`; the `callable` becomes a zero-arg sync calling
      `purge_expired_tokens.execute(retention_days=...)`. Remove
      `from arq.cron import CronJob, cron`

## 3. Rewrite `src/worker.py` as a runtime-agnostic scaffold

- [x] Remove every `arq` import: `from arq import run_worker`,
      `from arq.connections import RedisSettings`,
      `from arq.cron import CronJob`, `from arq.typing import
      StartupShutdown` / `WorkerCoroutine`, `from arq.worker import
      Function`, `from features.background_jobs.adapters.outbound.arq
      import build_arq_functions, job_handler_logging_startup`
- [x] Remove the `WorkerSettings` class, the `build_arq_functions(...)`
      call, `RedisSettings.from_dsn(...)`, `_wrap_relay_tick`, the
      `cron_job.coroutine = cast("WorkerCoroutine", ...)` arq-typing
      block, and `run_worker(...)`
- [x] Keep all container construction (email/jobs/outbox/users/
      file-storage), handler registration (`send_email`,
      `delete_user_assets`, `erase_user` with their
      `build_handler_dedupe` dedupe), `registry.seal()`, the engine/
      Redis construction, and the engine-dispose / redis-close /
      tracing-flush logic (as plain reusable helpers — the future
      runtime re-binds them; only the arq `on_shutdown` *binding* goes)
- [x] Collect the relay + auth-purge cron descriptors via the new
      `build_relay_cron_specs` / `build_auth_maintenance_cron_specs`
- [x] `main()`: build the scaffold (so composition errors still surface
      loudly), log the registered handlers + collected `CronSpec`s, then
      `return`/`sys.exit` **non-zero** with a clear message: no
      background-job runtime is wired — `arq` removed in ROADMAP ETAPA I
      step 5; the production worker runtime (AWS SQS + Lambda) arrives at
      ROADMAP steps 26–27; `make worker` will not process jobs until then

## 4. Settings surface

- [x] In `src/app_platform/config/settings.py`: narrow `jobs_backend`
      to `Literal["in_process"]`; remove `jobs_redis_url`,
      `jobs_queue_name`, `jobs_keep_result_seconds_default`,
      `jobs_max_jobs`, `jobs_job_timeout_seconds` and their comment
      block; reword the `in_process`/`arq` description so it states
      `in_process` is the only backend and production has no job runtime
      until AWS SQS (a later roadmap step)
- [x] In `src/features/background_jobs/composition/settings.py`: narrow
      `JobsBackend` to `Literal["in_process"]`; remove the arq-only
      fields from `JobsSettings` and from the `_JobsAppSettings`
      Protocol; remove the matching `from_app_settings` kwargs and the
      `app.jobs_*` assignments; narrow the
      `backend not in ("in_process", "arq")` guard + message to
      `("in_process",)`; delete the `if self.backend == "arq":` block in
      `validate()`; reword `validate_production` so it still appends an
      error when `backend == "in_process"` but the message no longer
      names `arq`/`APP_JOBS_REDIS_URL` (state no production job backend
      exists yet — AWS SQS arrives at a later roadmap step)

## 5. Composition + call sites

- [x] In `src/features/background_jobs/composition/container.py`: remove
      the entire `elif settings.backend == "arq":` arm (redis-url guard,
      `redis_lib is None` guard, the deferred `from arq import
      constants` and `from ...arq import ArqJobQueueAdapter`, adapter
      construction, the `owned_client`/`_shutdown` lifecycle for the
      arq-owned client). `in_process` becomes the only branch; keep the
      trailing defensive `else: raise RuntimeError`. Audit the
      module-level `try: import redis as redis_lib` block — remove it iff
      no surviving branch references `redis_lib` (likely removable here;
      the shared rate-limit/cache Redis client is owned by `src/main.py`,
      not by the jobs container after the arq arm is gone — confirm with
      a grep). Do **not** remove the `redis` *dependency*
- [x] In `src/main.py`: drop the `redis_url=` and `queue_name=` kwargs
      from the `JobsSettings.from_app_settings(...)` call (now unknown on
      the narrowed projection); remove the "the arq adapter reuses the
      shared rate-limit/cache Redis URL" comment; reword the
      `uv sync --extra worker` hint in the redis-missing `RuntimeError`
      so it does not imply arq (the redis dep / rate-limit-cache wiring
      itself is unchanged)

## 6. Config files and tooling

- [x] In `.env.example`: remove the arq `APP_JOBS_*` lines (the
      `arq:queue` default and any arq tunables); reword the
      `# Background-jobs.` comment so it no longer names
      `arq`/`APP_JOBS_REDIS_URL` (state `in_process` is the only
      backend; the production job runtime arrives with AWS SQS at a
      later roadmap step)
- [x] In `pyproject.toml`: remove `"arq~=0.26"` from the `worker`
      optional-dependency extra (**keep `redis`** — auth rate limiter +
      principal cache need it); remove `"arq~=0.26"` from the `dev`
      group (**keep `fakeredis`** — surviving rate-limit/principal-cache
      tests import it); reword the `worker = [...]` comment and the
      `uv sync --extra worker  # ... pulls arq + redis` install-modes
      comment so they no longer name arq (state the real worker runtime
      arrives at ROADMAP step 26/27). **Do NOT touch** the `arq + redis`
      Renovate co-version group (deferred — see proposal/audit), the
      runtime `redis` dependency, or any `redis` Import Linter guardrail
- [x] Run `uv lock` so `uv.lock` drops `arq` and arq-only transitives;
      confirm `redis`/`fakeredis` and their transitives remain. Commit
      the regenerated lock
- [x] In `Dockerfile`: keep the `runtime-worker` / `builder-worker` /
      `runtime-base` stages and `CMD ["python", "-m", "worker"]`; update
      the stage comments to state the worker runtime is not wired until
      ROADMAP step 26/27 (the image builds, the container exits loudly).
      **Do NOT delete the stage** (step 27 owns its revival)
- [x] In `Makefile`: keep the `worker` and `docker-build-worker`
      targets; reword the `worker:` `## ...` help text so it no longer
      says "Run the arq background-jobs worker" — state the worker
      runtime is not available until ROADMAP step 26/27 (running it
      exits non-zero with that message)
- [x] `docker-compose.yml`: audited — no `worker` service ships and the
      `redis` service stays (rate-limit/cache). **No edit required**;
      re-confirm with a grep during implementation

## 7. Tests

- [x] Delete `src/features/background_jobs/tests/unit/test_arq_adapter.py`
- [x] Delete
      `src/features/background_jobs/tests/unit/test_arq_adapter_metrics.py`
- [x] Delete
      `src/features/background_jobs/tests/unit/test_arq_worker_settings.py`
- [x] Delete
      `src/features/background_jobs/tests/integration/test_arq_round_trip.py`
- [x] Delete
      `src/features/background_jobs/tests/integration/test_arq_redis_round_trip.py`
- [x] In
      `src/features/background_jobs/tests/contracts/test_job_queue_port_contract.py`:
      remove `from features.background_jobs.adapters.outbound.arq import
      ArqJobQueueAdapter`, the `import fakeredis` (only the arq factory
      used it in this file), the `_arq_factory`, and the `arq`
      parametrisation id. Parametrise
      `test_enqueue_succeeds_for_registered_job` /
      `test_enqueue_unknown_job_raises` over `[in_process, fake]`. In
      `test_enqueue_at_succeeds_for_registered_job_on_scheduling_adapters`
      drop the `_arq_factory` line, keep the `_fake_factory` line.
      Parametrise `test_enqueue_at_unknown_job_raises` over `[fake]`.
      Keep `test_in_process_adapter_refuses_enqueue_at` verbatim
- [x] Reword the `InProcessJobQueueAdapter.enqueue_at` docstring so it
      no longer says "set APP_JOBS_BACKEND=arq for scheduled execution"
      (state: scheduled execution requires the production job runtime,
      added at a later roadmap step)
- [x] Rewrite (or delete + replace) `src/tests/unit/test_worker_graceful_shutdown.py`:
      the arq `on_shutdown` / `_wrap_relay_tick` it targets is gone.
      Re-scope to assert the surviving scaffold — the engine-dispose /
      redis-close / tracing-flush helpers are still callable, and
      `worker.main()` exits non-zero with the "no runtime wired"
      message. Drop the `_RELAY_TICK_*` autouse fixture lines that
      reference removed globals
- [x] Add/keep unit coverage for `build_relay_cron_specs` and
      `build_auth_maintenance_cron_specs`: assert interval snapping, the
      `APP_OUTBOX_ENABLED=false` empty-list gate, the
      `interval_minutes <= 0` kill-switch empty-list gate, and the
      descriptor `name`/`interval_seconds`/`run_at_startup` values — the
      schedules stay tested without arq
- [x] In `src/app_platform/tests/test_settings.py`: remove
      `"APP_JOBS_BACKEND"` and `"APP_JOBS_REDIS_URL"` from
      `_VALID_PROD_ENV` entirely (no production-valid jobs value
      remains); **keep** `"APP_OUTBOX_ENABLED": "true"` (Key decision 3).
      Delete `test_arq_backend_requires_redis_url`. Keep/strengthen the
      `in_process`-refused-in-production test so it asserts
      `APP_ENVIRONMENT=production` raises a `ValidationError` whose
      message reports the jobs-backend problem and names no removed
      backend (no `arq`, no `APP_JOBS_REDIS_URL`). For every other test
      that loads `_VALID_PROD_ENV` and asserts a *different* refusal,
      isolate the now-always-present jobs-backend error so the assertion
      still targets its own env var
- [x] Audit (grep for `arq`) and confirm STAY untouched except for any
      arq-package import / arq-side assertion:
      `src/features/background_jobs/tests/unit/test_trace_propagation.py`
      (assert the in-process entrypoint attaches `__trace`; drop any
      arq-side assertion), `test_send_email_handler.py`,
      `test_registry.py`, `test_in_process_adapter.py`,
      `test_in_process_adapter_metrics.py`. Confirm none import the
      deleted arq package after this change

## 8. Docs (arq/worker-runtime lines only — no wholesale rewrite)

- [x] `docs/background-jobs.md`: drop the arq adapter / `make worker`
      arq-runtime / `APP_JOBS_REDIS_URL` / arq result-retention /
      Redis-eviction-policy content; state `APP_JOBS_BACKEND` accepts
      only `in_process`, production has no job runtime until AWS SQS
      (step 26) + the Lambda worker (step 27)
- [x] `docs/outbox.md`: the relay "runs inside the arq worker" wording →
      "runs inside the worker runtime; the runtime is added at a later
      roadmap step; the `outbox_messages` table and request-path writers
      are unchanged". Do NOT rewrite the broader narrative (step 11)
- [x] `docs/operations.md`: remove the arq `APP_JOBS_*` env-reference
      rows and the `uv sync --extra worker → arq` install-modes row;
      state the minimal accurate post-removal reality
      (`APP_JOBS_BACKEND` accepts only `in_process`; production deferred
      work not bootable until AWS SQS + Lambda; the
      `APP_OUTBOX_ENABLED=true` production refusal is unchanged). Do
      **not** rewrite the broader "production refuses to start if…"
      narrative — ROADMAP step 11 owns that
- [x] `docs/observability.md`: drop arq-worker-specific tracing/metrics
      lines that name arq; keep the surviving `app_jobs_enqueued_total`
      / in-process trace-propagation content
- [x] `docs/architecture.md`: the background-jobs feature row
      "in-process + arq adapters" → "in-process adapter (dev/test);
      production job runtime arrives with AWS SQS + Lambda at a later
      roadmap step"
- [x] `docs/development.md`: drop arq/`make worker` runtime instructions
      that name arq; state the worker runtime is added at a later
      roadmap step
- [x] `docs/email.md`: if it documents the `send_email` job running on
      the arq worker, reword to "the worker runtime (added at a later
      roadmap step)"; the `console`/`in_process` dev story is unchanged
- [x] `README.md`: feature-row / tree-comment / key-env-var lines that
      name `arq`/`APP_JOBS_REDIS_URL` → state `in_process` is the only
      backend, production job runtime not yet available (AWS SQS +
      Lambda later). Do NOT rewrite the feature matrix (step 9)
- [x] `CLAUDE.md`: the background-jobs feature-table row, the
      `make worker` command line, the `APP_JOBS_BACKEND` /
      `APP_JOBS_REDIS_URL` key-env-var rows, and the
      `APP_JOBS_BACKEND=in_process` production-checklist bullet → state
      `in_process` is the only backend and the production job runtime is
      not yet available (AWS SQS + Lambda at a later roadmap step). Do
      NOT do the step-10 CLAUDE rewrite
- [x] `CONTRIBUTING.md`: **line-by-line audit** (the step-4 audit
      initially missed real `CONTRIBUTING.md` refs). Correct real
      arq/worker-runtime references (e.g. commit-subject examples naming
      arq, a pre-deploy checklist item asserting `APP_JOBS_BACKEND=arq`);
      leave the generic English word "worker" and the generic
      "background job" concept untouched. Record in this task which
      lines were real refs vs left untouched

## 9. Verify

- [x] `make lint-arch` — no new Import Linter violation; specifically
      the `CronSpec` import edge from `outbox`/`authentication`
      `composition/worker.py` and from `src/worker.py` is allowed
- [x] `make quality` green (lint + arch + typecheck) — no dangling
      `WorkerSettings`/`CronJob`/`arq` annotation or import
- [x] `make test` green; the job-queue contract suite passes for
      `in_process` and `fake`; the relay/auth-purge `CronSpec` tests
      pass; the `_VALID_PROD_ENV` reconciliation leaves every other
      production-refusal test asserting its own target
- [x] `grep -rin '\barq\b\|APP_JOBS_REDIS_URL\|run_worker\|WorkerSettings'
      src docs *.md .env.example pyproject.toml Dockerfile Makefile`
      returns no arq hit other than: the kept `arq + redis` Renovate
      group / its `quality-automation` spec scenario (deferred — see
      proposal), and any `CONTRIBUTING.md` generic-English "worker" /
      generic "background job" lines deliberately left
- [x] `openspec validate remove-arq-adapter --strict` passes
