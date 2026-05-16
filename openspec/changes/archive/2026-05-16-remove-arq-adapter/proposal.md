## Why

ROADMAP ETAPA I step 5 ("dejar el repo honesto"): remove the `arq`
background-jobs adapter and every config/test/doc surface that promises
it. Steps 3 and 4 already deleted the SMTP and Resend email adapters
under the same explicit ROADMAP decision — *remove non-AWS
production-shaped adapters (SMTP, Resend, arq, SpiceDB), keep dev-only
adapters (`in_process`), add the real AWS adapter much later* (`aws_sqs`
is ROADMAP step 26, the Lambda worker is step 27, the outbox→bus cutover
is step 28). The `arq` backend no longer pays its way:

1. **`arq` is not just an adapter — it is the worker *runtime*.**
   `src/worker.py` (399 lines) is the `arq` worker entrypoint
   (`from arq import run_worker`, `arq.connections.RedisSettings`,
   `arq.cron.CronJob`, `arq.worker.Function`, an `on_shutdown` hook that
   drains an in-flight relay tick and disposes the engine/Redis pool).
   `ArqJobQueueAdapter` writes arq-wire-compatible Redis keys from sync
   code; `build_arq_functions` / `job_handler_logging_startup` adapt the
   sync `JobHandler` registry to arq's `async (ctx, *args)` shape.
   `make worker` runs it; the `runtime-worker` Dockerfile stage ships
   it; `make docker-build-worker` builds it. The **outbox relay**
   (`DispatchPending`) and the **auth token-purge cron**
   (`PurgeExpiredTokens`) only ever run as `arq` cron jobs registered by
   `src/features/outbox/composition/worker.py` and
   `src/features/authentication/composition/worker.py` — both modules
   import `from arq.cron import CronJob, cron`.

2. **It widens the public config contract with knobs no one should
   set.** `AppSettings` carries `jobs_backend: Literal["in_process",
   "arq"]` plus six arq-only fields (`jobs_redis_url`,
   `jobs_queue_name`, `jobs_keep_result_seconds_default`,
   `jobs_max_jobs`, `jobs_job_timeout_seconds`); the `JobsSettings`
   projection mirrors them with an arq `validate()` branch; `.env.example`
   ships the `arq:queue` default; the `worker = ["arq~=0.26", ...]`
   optional-dependency extra and the `dev`-group `"arq~=0.26"` /
   `fakeredis` test deps exist solely for the arq adapter and its tests.
   An operator reading the env reference cannot tell the arq runtime is
   being retired ahead of AWS SQS.

3. **`jobs_backend` collapses to a single value.** With `arq` gone,
   `Literal["in_process", "arq"]` becomes `Literal["in_process"]` —
   `in_process` is the only backend. Every multi-backend branch (the
   `elif settings.backend == "arq":` arm in `build_jobs_container`, the
   `backend not in ("in_process", "arq")` guard, the arq `validate()`
   branch, the three-way contract parametrisation) is now a degenerate
   one-arm dispatch carrying a dead production runtime.

This step deletes the arq backend and its runtime only. `in_process`
(the dev/test fake) is unchanged and remains the sole adapter. The real
production job backend (`aws_sqs`) is ROADMAP step 26, the Lambda worker
is step 27, and the outbox→SNS/EventBridge cutover is step 28 — all
explicitly out of scope here.

### Sub-split assessment (ROADMAP rule, line 18)

This step is materially larger and more entangled than steps 3–4: arq
is the worker *runtime*, not just an `EmailPort`-style dispatch leaf.
Removing it forces decisions about `src/worker.py`, the outbox relay,
and the auth purge cron — none of which existed for SMTP/Resend. Per
the ROADMAP rule "*si un paso resulta más grande de lo esperado, lo
partimos en sub-pasos pero seguimos en orden*", **this step is split
into two ordered sub-steps and THIS change is scoped to sub-step 5a
only.** The split, the boundary rationale, and why 5a is internally
coherent and shippable on its own are argued in full in `design.md`
(§"Sub-split decision"). In short:

- **5a (this change): remove the arq adapter + arq runtime; collapse
  `jobs_backend` to `in_process`; convert `src/worker.py` and the two
  per-feature cron modules to a runtime-agnostic composition-root +
  handler/cron registry scaffold (no `arq` import anywhere); update
  config/tests/docs/spec deltas; keep every production-safety refusal
  honest.** Self-contained: `make quality` + `make test` green, no arq
  symbol anywhere, the shared composition root + handler/cron registry
  preserved so steps 26–27 can re-attach a real runtime.
- **5b (next change, NOT this one): the `aws_sqs` adapter + Lambda
  worker runtime** — that is ROADMAP step 26/27, explicitly a later
  step. 5a does not pre-empt it; it leaves a clean seam.

The `worker` extra, `pyproject.toml`, and `uv.lock` edits stay in 5a
(not deferred): they are intrinsic to "remove arq" exactly as the
`resend` extra removal was intrinsic to step 4, and leaving a
`worker = ["arq~=0.26"]` extra after deleting every arq import would be
the dead-config dishonesty this ROADMAP step exists to eliminate.

### Key decision 1 — `src/worker.py` is preserved as a runtime-agnostic scaffold, not deleted

ROADMAP step 27 explicitly expects `src/worker.py` to still
conceptually exist ("*misma raíz de composición que `src/main.py` y
`src/worker.py`*"). Deleting it would strand step 27. Keeping it with
`arq` imports stripped but `run_worker`/`WorkerSettings`/`CronJob`
references dangling would not type-check. **Decision: reduce
`src/worker.py` to a non-arq composition-root + handler/cron-registry
scaffold.** It SHALL still call `get_settings()`, build the
email/jobs/outbox/users containers exactly as today, register every
handler (`send_email`, `delete_user_assets`, `erase_user`), seal the
registry, and collect the relay + auth-purge "cron specs" — but it
SHALL NOT import `arq`, construct `arq.WorkerSettings`, or call
`run_worker`. Its `main()` SHALL exit with a clear, non-zero message
stating that no job runtime is wired until the AWS SQS/Lambda worker
arrives (ROADMAP step 26/27) — the same "honest refusal over a silent
no-op" stance the production validator takes. The per-feature
`composition/worker.py` modules (`outbox`, `authentication`) are
rewritten to return runtime-agnostic cron *descriptors*
(`(name, interval, callable)` dataclasses) instead of `arq.cron.cron(...)`
objects, so the relay/purge schedules are still *declared and unit-
tested* and step 27 only has to bind them to a real scheduler.
Rationale and the descriptor shape are in `design.md`.

### Key decision 2 — every production-safety refusal stays a refusal (steps 3/4 precedent)

Removing arq leaves `in_process` as the only `jobs_backend` value. The
jobs production validator currently refuses `in_process` when
`APP_ENVIRONMENT=production`
(`src/features/background_jobs/composition/settings.py`,
`validate_production`). After this step there is **no production-capable
job backend at all** until ROADMAP step 26 adds `aws_sqs`.

**Decision: keep the refusal honest — the validator SHALL continue to
refuse `in_process` in production.** Production-with-deferred-work is
intentionally not bootable until SQS + the Lambda worker arrive. This is
identical to the step-4 email decision and correct for the same three
reasons:

- **Safety invariant preserved.** The refusal exists so production never
  silently runs the in-process queue, which executes "deferred" work
  *inline in the request thread and loses every queued job on restart*.
  That risk does not disappear because `in_process` became the only
  value; it gets worse (no safe alternative). Relaxing it so production
  boots on `in_process` would come up "green" while `send_email`,
  `delete_user_assets`, and `erase_user` run synchronously in the
  request path and the outbox relay never runs at all. An explicit boot
  failure is strictly safer than that silent degradation.
- **Honest over convenient.** The honest post-step-5 statement is: *this
  starter has no production job runtime yet; it arrives at ROADMAP step
  26/27*. A validator that refuses to boot says exactly that.
- **Minimal blast radius, no roadmap pre-emption.** The only forced
  change is wording: the message currently says "configure 'arq' and set
  APP_JOBS_REDIS_URL"; `arq` no longer exists, so the message must stop
  naming it and instead state no production job backend exists yet
  (AWS SQS at a later roadmap step). This does NOT pre-empt ROADMAP
  step 11 (operations.md narrative) or step 26 (the SQS adapter and its
  accept-path).

Considered and rejected: *relax the jobs refusal so production may boot
on `in_process`* — rejected for the same reason step 4 rejected the
console analogue: it converts a loud "not ready yet" into a silent
production degradation (synchronous request-path job execution + a
never-running outbox relay).

### Key decision 3 — the outbox-relay / `APP_OUTBOX_ENABLED` production requirement stays a refusal too

The outbox production validator
(`src/features/outbox/composition/settings.py`,
`OutboxSettings.validate_production`) refuses startup when
`APP_OUTBOX_ENABLED=false` in production, and the relay only ever runs
inside the worker runtime. Removing the arq runtime means production now
*demands* the relay be enabled yet *nothing can run it* until ROADMAP
step 26/27. This is the same "intentionally not bootable until the AWS
adapter lands" state as decisions 1 and 2 — **fully consistent with the
steps-3/4 precedent and the cleanest option.**

**Decision: do NOT weaken the `APP_OUTBOX_ENABLED=true` production
requirement.** Production-with-deferred-work is not bootable until step
26/27; that is the honest mid-cleanup truth, not a regression introduced
here. Narrowing or removing the outbox production assertion to make
production "boot again" would silently weaken a production-safety
invariant (request-path consumers write to the outbox unconditionally;
a disabled relay means those rows are written and never delivered) and
would pre-empt ROADMAP step 28 (outbox→bus) and step 11 (operations.md
narrative). The minimal accurate post-step-5 reality, stated in the
spec deltas and the narrowly-scoped doc edits, is: *production with
deferred work is intentionally not bootable until the AWS SQS adapter
(step 26) and the Lambda worker (step 27); the outbox table and its
request-path writers are unchanged, only the runtime that drains it is
removed.* Considered and rejected: *flip the outbox prod requirement to
a warning* — rejected (silently weakens a safety invariant, pre-empts
steps 11/28). See `design.md` §"Outbox-relay coherence".

### `worker`-extra / `redis` audit conclusion (the careful part)

`pyproject.toml` references arq/worker in five roles. The audit (full
reasoning in `design.md` §"Dependency audit"):

- `worker = ["arq~=0.26", "redis~=5.2"]` optional extra — **the `arq`
  entry is removed**. The extra itself is **kept but emptied of arq**:
  `redis` SHALL stay because the auth rate limiter *and* the principal
  cache use `redis` directly (`build_jobs_container` and `src/main.py`
  both `import redis as redis_lib` for the shared client; the
  rate-limit/cache layer needs it independent of jobs). Removing `redis`
  would break distributed rate limiting and the principal cache —
  out of scope and a production-safety regression. The extra is renamed
  conceptually to "the Redis-using roles" but, to keep blast radius
  minimal and not pre-empt step 26's naming, this change keeps the
  `worker` key with `redis` only and a comment that arq was removed and
  the real worker runtime arrives at ROADMAP step 26/27. (Whether to
  rename the extra is deferred — it is cosmetic and a renovate/spec
  concern; see `design.md`.)
- `dev`-group `"arq~=0.26"` — **removed** (only the arq adapter/tests
  imported it). `fakeredis` in `dev` — **audited**: a repo-wide search
  shows `fakeredis` is imported by the job-queue contract test (the arq
  factory, removed here) **and** by auth rate-limiter / principal-cache
  tests that exercise the `redis` path. `fakeredis` is therefore
  **kept** — removing it would break the surviving Redis-backed tests.
- `arq` / `redis` Renovate co-version group in
  `renovate.json` / the `quality-automation` spec — the `arq + redis`
  group entry still names `arq`. **Kept untouched in 5a**: editing
  `renovate.json` and its spec scenario is a dependency-grouping
  concern, the group is harmless with arq absent (Renovate simply finds
  no `arq` to update), and reconciling the renovate group cleanly
  belongs with the AWS-SQS naming decision (ROADMAP step 26) or the
  doc-rewrite steps (9/10/11). Touching it here would pre-empt a naming
  decision not yet made. Flagged explicitly so the omission is auditable.
- `redis` in the Import Linter `forbidden_modules` lists (if present) /
  the runtime `redis` dependency for rate-limit/cache — **kept,
  untouched** (architectural/rate-limit scope, not arq scope).
- `uv lock` MUST be regenerated after the `pyproject.toml` edits so the
  lockfile drops `arq` and its transitive deps; `redis`/`fakeredis`
  stay.

## What Changes

- Delete the arq adapter package
  `src/features/background_jobs/adapters/outbound/arq/`
  (`__init__.py`, `adapter.py`, `worker.py`).
- Rewrite `src/worker.py` as a **runtime-agnostic composition-root +
  handler/cron-registry scaffold** (Key decision 1): keep all container
  construction, handler registration, registry sealing, and cron-spec
  collection; remove every `arq` import (`run_worker`, `RedisSettings`,
  `CronJob`, `Function`, `StartupShutdown`, `WorkerCoroutine`,
  `serialize_job`), the `WorkerSettings` class, `build_arq_functions`
  usage, and the arq-specific `on_shutdown`/`_wrap_relay_tick`
  plumbing. `main()` exits non-zero with a clear message that no job
  runtime is wired until the AWS SQS/Lambda worker (ROADMAP step
  26/27). The shared shutdown-drain *intent* is preserved as a
  documented hook the future runtime re-attaches (the engine/Redis
  dispose helpers stay; only the arq `on_shutdown` binding goes).
- Rewrite `src/features/outbox/composition/worker.py` and
  `src/features/authentication/composition/worker.py` to return
  runtime-agnostic cron **descriptors** (a small
  `CronSpec(name, interval, run_at_startup, callable)` dataclass owned
  by the background-jobs feature) instead of `arq.cron.cron(...)`
  `CronJob` objects. The interval-snapping logic and the
  enabled/kill-switch gating are preserved verbatim; only the arq
  binding is removed. Relay + purge schedules remain declared and
  unit-tested.
- Narrow `jobs_backend` from `Literal["in_process", "arq"]` to
  `Literal["in_process"]` and remove the six arq-only fields
  (`jobs_redis_url`, `jobs_queue_name`,
  `jobs_keep_result_seconds_default`, `jobs_max_jobs`,
  `jobs_job_timeout_seconds`) plus their comment block from
  `AppSettings` (`src/app_platform/config/settings.py`). Reword the
  `in_process`/`arq` description comment to state `in_process` is the
  only backend and production has no job runtime until AWS SQS.
- In `src/features/background_jobs/composition/settings.py`: narrow
  `JobsBackend` to `Literal["in_process"]`; remove the arq-only fields
  from `JobsSettings` and the `_JobsAppSettings` Protocol; narrow the
  `backend not in (...)` guard to `("in_process",)`; remove the
  `if self.backend == "arq":` branch from `validate()`; reword
  `validate_production` so it still refuses `in_process` but its message
  no longer names `arq`/`APP_JOBS_REDIS_URL` — it states no production
  job backend exists yet (AWS SQS at a later roadmap step).
- In `src/features/background_jobs/composition/container.py`: remove the
  `elif settings.backend == "arq":` arm (redis-url guard, the
  `redis_lib is None` guard, the deferred `from arq import constants`
  and `from ...arq import ArqJobQueueAdapter` imports, adapter
  construction, the owned-client lifecycle); `in_process` becomes the
  only branch. Keep the final defensive `else: raise RuntimeError`.
  Audit the module-level `try: import redis` block — it is **kept** if
  any surviving branch still needs the shared client passthrough;
  otherwise removed (confirm during implementation; the shared `redis`
  client is owned by `src/main.py`'s rate-limit/cache wiring, not by the
  jobs container after the arq arm is gone — likely removable here, but
  removing `redis` the *dependency* is out of scope).
- In `src/main.py`: the `build_jobs_container(JobsSettings.from_app_settings(
  backend=..., redis_url=..., queue_name=...))` call drops the
  `redis_url`/`queue_name` kwargs (now unknown on the narrowed
  projection); the comment about "the arq adapter reuses the shared
  rate-limit/cache Redis URL" is removed. The shared-redis wiring for
  rate limiting / principal cache is **untouched** (it is not jobs
  scope; the `uv sync --extra worker` hint in the redis-missing
  `RuntimeError` is reworded to not imply arq).
- Remove the `arq:queue` jobs default and any `APP_JOBS_*` arq-tunable
  lines from `.env.example`; reword the `# Background-jobs.` comment so
  it no longer names `arq`/`APP_JOBS_REDIS_URL` (state `in_process` is
  the only backend; production job runtime arrives with AWS SQS later).
- In `pyproject.toml`: remove `"arq~=0.26"` from the `worker` extra
  (keep `redis` — rate-limit/cache need it; see audit) and the
  `# ... pulls arq + redis` install-modes comment wording that names
  arq; remove `"arq~=0.26"` from the `dev` group (keep `fakeredis` —
  surviving Redis tests need it); reword the `worker = [...]` comment to
  state arq was removed and the real worker runtime arrives at ROADMAP
  step 26/27. Regenerate `uv.lock` via `uv lock`.
- In the `Dockerfile`: the `runtime-worker` stage and
  `builder-worker`/`runtime-base` plumbing currently `uv sync
  --extra worker` and `CMD ["python", "-m", "worker"]`. The stage is
  **kept** (step 27 needs a worker image seam) but its `CMD` now points
  at a `src/worker.py` that exits non-zero "no runtime wired yet" — this
  is acceptable and honest (the image builds, the container exits
  loudly). Update the stage comment to state the worker runtime is not
  wired until ROADMAP step 26/27; do NOT delete the stage (out of scope,
  step 27 owns its revival). `make docker-build-worker` is **kept**.
- `Makefile`: the `worker` target (`PYTHONPATH=src uv run python -m
  worker`) is **kept** but its `## ...` help text is reworded — it no
  longer claims to "Run the arq background-jobs worker"; it states the
  worker runtime is not available until ROADMAP step 26/27 (running it
  exits non-zero with that message). `docker-build-worker` kept.
- `docker-compose.yml`: audited — it ships **no** `worker` service
  (only `redis`/`db`/`migrate`/`app`). The `redis` service stays (auth
  rate limiter / principal cache use it). **No compose edit required.**
- Delete the arq-only tests:
  `src/features/background_jobs/tests/unit/test_arq_adapter.py`,
  `test_arq_adapter_metrics.py`, `test_arq_worker_settings.py`,
  `src/features/background_jobs/tests/integration/test_arq_round_trip.py`,
  `test_arq_redis_round_trip.py`.
- De-parametrise
  `src/features/background_jobs/tests/contracts/test_job_queue_port_contract.py`:
  drop the `_arq_factory`, the `arq` parametrisation id, the
  `from ...arq import ArqJobQueueAdapter` and `import fakeredis` lines
  for the arq factory; keep `in_process` and `fake`. The two
  `enqueue_at` scenarios currently rely on `_arq_factory`/`_fake_factory`
  (in_process refuses scheduling); they are re-pointed to `_fake_factory`
  only (the fake supports `enqueue_at`), and the
  `test_in_process_adapter_refuses_enqueue_at` pin is kept (it asserts
  the surviving in_process surface). See `design.md` for the exact
  contract-test reshape.
- Rewrite `src/tests/unit/test_worker_graceful_shutdown.py`: the arq
  `on_shutdown`/`_wrap_relay_tick` it targets is removed. The test is
  re-scoped to assert the preserved runtime-agnostic scaffold (engine/
  Redis dispose helpers still callable; `main()` exits non-zero with the
  "no runtime wired" message) — or deleted and replaced by a new
  `test_worker_scaffold.py` if cleaner. The graceful-shutdown *spec*
  requirement is MODIFIED (see deltas) so the API lifespan drain
  guarantee is unchanged and the worker `on_shutdown` clause becomes
  "the future job runtime SHALL implement the drain"; the API-side
  graceful-shutdown tests are untouched.
- In `src/app_platform/tests/test_settings.py`: repoint the shared
  `_VALID_PROD_ENV` baseline — `APP_JOBS_BACKEND` is removed from it
  entirely (no production-valid value remains; `in_process` is now the
  only value and it is always refused in production), drop
  `APP_JOBS_REDIS_URL`; the `APP_OUTBOX_ENABLED=true` entry stays
  (Key decision 3 — the outbox prod requirement is unchanged). Delete
  `test_arq_backend_requires_redis_url`; keep/strengthen the
  `in_process`-refused-in-production test so its message names no
  removed backend; isolate the now-always-present jobs-backend refusal
  in every other `_VALID_PROD_ENV`-based production test so each still
  asserts its own target refusal (mirrors the step-4 ripple).
- Audit `src/features/background_jobs/tests/unit/test_trace_propagation.py`,
  `test_send_email_handler.py`, `test_registry.py`,
  `test_in_process_adapter*.py`: these exercise the surviving
  `in_process` adapter / registry / trace-propagation and STAY — verify
  none import the arq package (the trace-propagation test asserts the
  *in-process* entrypoint attaches `__trace`; the arq-side assertion, if
  any, is dropped with the arq worker).
- Remove arq/worker-runtime lines **only** from `docs/background-jobs.md`,
  `docs/outbox.md`, `docs/operations.md`, `docs/observability.md`,
  `docs/architecture.md`, `docs/development.md`, `docs/email.md`,
  `README.md`, `CLAUDE.md`, and `CONTRIBUTING.md`. State the minimal
  accurate post-removal reality: `APP_JOBS_BACKEND` accepts only
  `in_process`; production has no job runtime until AWS SQS (step 26) +
  the Lambda worker (step 27); the outbox table and its request-path
  writers are unchanged, only the runtime that drains it is removed. Do
  NOT rewrite the broader "production refuses to start if…" narrative
  (ROADMAP step 11) or the README/CLAUDE feature-matrix (steps 9/10).
  Audit `CONTRIBUTING.md` line-by-line: distinguish real arq/worker-
  runtime references (corrected) from the generic English word "worker"
  / generic "background job" concept (left untouched) — the step-4 audit
  initially missed real `CONTRIBUTING.md` references, so this audit is
  explicit and line-by-line.

**Production-validator coherence (required by the constraint):** the
jobs production validator continues to refuse `in_process` in production
(Key decision 2). The outbox production validator continues to refuse
`APP_OUTBOX_ENABLED=false` in production (Key decision 3). The only
forced changes are wording (the jobs message no longer names `arq`) and
the spec restatement that production-with-deferred-work is intentionally
not bootable until AWS SQS + the Lambda worker. This does not pre-empt
ROADMAP step 11 (operations.md narrative), step 26 (SQS adapter), step
27 (Lambda worker), or step 28 (outbox→bus).

**Capabilities — Modified**
- `background-jobs`: all four requirements are entangled with arq. The
  self-contained-feature and adapter-selection requirements no longer
  enumerate `arq`/`APP_JOBS_REDIS_URL` (only `in_process`); the
  worker-entrypoint requirement is restated as "a runtime-agnostic
  worker composition-root scaffold exists; the real runtime arrives with
  AWS SQS/Lambda at a later roadmap step"; the production guard is
  restated as "refuses `in_process`, no production job backend is
  accepted".
- `outbox`: the `Worker integration` requirement no longer names the
  `arq` worker — it is restated as "the worker scaffold collects the
  relay cron descriptor when `APP_OUTBOX_ENABLED=true`; the real
  scheduler arrives at a later roadmap step; the web process still never
  runs the relay; the `APP_OUTBOX_ENABLED=true` production refusal is
  unchanged". The `Outbox carries W3C trace context end-to-end`
  requirement's "(both in-process and arq)" parenthetical narrows to
  in-process. The PruneOutbox-CLI requirement is unchanged (it is a
  standalone CLI, not arq).
- `project-layout`: the `arq worker has bounded result retention`
  requirement is REMOVED (it is wholly an arq-`WorkerSettings`/
  `keep_result` requirement; result-retention is a SQS/Lambda concern
  for step 26). `Process shutdown is graceful and bounded` is MODIFIED:
  the API lifespan drain is unchanged; the "arq worker SHALL implement
  `on_shutdown`…" clause becomes "the future job runtime SHALL implement
  the equivalent drain". `Dockerfile exposes a dedicated worker stage`
  is MODIFIED: the stage still exists and reuses the hardened base, but
  the "starts the arq worker" scenario becomes "runs the worker
  scaffold, which exits non-zero until the AWS SQS/Lambda runtime is
  wired (later roadmap step)". `Strategic Any/object hotspots are typed`
  is MODIFIED: the arq `WorkerSettings`/`CronJob` typing clause is
  dropped (those symbols no longer exist); the `_principal_from_user`
  clause is carried forward unchanged. `Entrypoints reference modules by
  their real names` keeps `worker` as a real module name (the scaffold
  is still `python -m worker`) — restated only to drop the "arq worker"
  phrasing.
- `quality-automation`: `Runtime dependencies are split into core, api,
  worker, and adapter extras` is MODIFIED — the `worker` extra no longer
  lists `arq` (it lists `redis`, kept for rate-limit/cache); the
  "Worker role install brings arq and redis" scenario becomes "brings
  redis (no arq; the worker runtime arrives at a later roadmap step)".
  The `Renovate ... arq + redis group` requirement is **NOT modified
  here** (flagged in the audit; renovate-group reconciliation is
  deferred to the SQS-naming/doc-rewrite steps).
- `authentication`: `Every documented production refusal has a unit
  test` is restated so the jobs-backend refusal it implies is "no
  production job backend exists" (not "in_process refused / arq
  accepted"), with no accept-path test; the outbox refusal clause is
  carried forward unchanged (Key decision 3).

**Capabilities — New**
- None.

## Impact

- **Deleted package**:
  `src/features/background_jobs/adapters/outbound/arq/`
  (`__init__.py`, `adapter.py`, `worker.py`).
- **`src/worker.py` fate**: **kept, rewritten** as a runtime-agnostic
  composition-root + handler/cron-registry scaffold with no `arq`
  import; `main()` exits non-zero "no job runtime wired until ROADMAP
  step 26/27". (Not deleted — step 27 needs the seam; not left with
  dangling arq imports — would not type-check.)
- **Code**:
  - `src/app_platform/config/settings.py` (narrow `jobs_backend`;
    remove six arq fields + comment block; reword comment)
  - `src/features/background_jobs/composition/settings.py` (narrow
    `JobsBackend` + `_JobsAppSettings` + guard; remove arq fields;
    drop the arq `validate()` branch; reword `validate_production`)
  - `src/features/background_jobs/composition/container.py` (remove the
    arq arm + deferred arq imports + owned-client lifecycle; audit the
    module-level `import redis` block)
  - `src/main.py` (drop `redis_url`/`queue_name` kwargs from the
    `JobsSettings.from_app_settings` call; reword the arq comment and
    the redis-missing `RuntimeError` hint)
  - `src/worker.py` (full rewrite per Key decision 1)
  - `src/features/outbox/composition/worker.py` (return `CronSpec`
    descriptors, not `arq.cron.cron(...)`; keep snapping + gating)
  - `src/features/authentication/composition/worker.py` (same reshape)
  - new `CronSpec` dataclass under
    `src/features/background_jobs/` (runtime-agnostic cron descriptor;
    exact module path decided in implementation — likely
    `application/cron.py` so both feature modules and the worker
    scaffold can import it without crossing a feature boundary; verify
    against Import Linter)
  - `.env.example` (remove arq `APP_JOBS_*` lines; reword comment)
  - `pyproject.toml` (drop `arq` from the `worker` extra and the `dev`
    group; keep `redis`/`fakeredis`; reword comments)
  - `uv.lock` (regenerate via `uv lock`; drops `arq` + arq-only
    transitives; `redis`/`fakeredis` stay)
  - `Dockerfile` (reword the `runtime-worker`/`builder-worker` stage
    comments; stage + `CMD` kept — image builds, container exits loudly)
  - `Makefile` (reword the `worker` target help text; target + the
    `docker-build-worker` target kept)
- **`docker-compose.yml`**: **no edit** (no `worker` service ships;
  `redis` stays for rate-limit/cache). Audited and confirmed.
- **Dependency audit conclusion**: (1) `worker` extra — `arq`
  **removed**, `redis` **kept** (auth rate limiter + principal cache
  import `redis` directly, independent of jobs). (2) `dev` group — `arq`
  **removed**, `fakeredis` **kept** (a repo-wide search shows surviving
  rate-limit/principal-cache tests import `fakeredis`; only the arq
  contract factory's use goes). (3) the `arq + redis` Renovate
  co-version group / its `quality-automation` spec scenario — **kept
  untouched, flagged**: editing it pre-empts the AWS-SQS naming decision
  (step 26) and the doc-rewrite steps; the group is inert with arq
  absent. (4) the runtime `redis` dependency and any `redis` Import
  Linter guardrail — **kept, untouched** (rate-limit/cache scope, not
  arq scope). (5) `uv lock` regenerated.
- **Tests**:
  - Delete `test_arq_adapter.py`, `test_arq_adapter_metrics.py`,
    `test_arq_worker_settings.py`,
    `tests/integration/test_arq_round_trip.py`,
    `test_arq_redis_round_trip.py`.
  - De-parametrise `test_job_queue_port_contract.py` (drop the arq
    factory/id/`fakeredis`-for-arq/`ArqJobQueueAdapter` import; keep
    `in_process` + `fake`; re-point the `enqueue_at` scenarios to the
    fake factory; keep the in_process-refuses-enqueue_at pin).
  - Rewrite (or replace) `src/tests/unit/test_worker_graceful_shutdown.py`
    to target the surviving runtime-agnostic scaffold rather than the
    deleted arq `on_shutdown`.
  - `src/app_platform/tests/test_settings.py`: drop `APP_JOBS_BACKEND`/
    `APP_JOBS_REDIS_URL` from `_VALID_PROD_ENV` (no production-valid
    jobs value remains — this is the "when no production-valid value
    remains, repoint to the dev value and isolate the now-always-present
    refusal" ripple from memory `etapa1-adapter-removal`); keep
    `APP_OUTBOX_ENABLED=true` (Key decision 3); delete
    `test_arq_backend_requires_redis_url`; strengthen the
    `in_process`-refused test (message names no removed backend);
    isolate the always-present jobs refusal in every other
    `_VALID_PROD_ENV` production test.
  - Add/keep unit coverage for the new `CronSpec` descriptors so the
    relay + auth-purge schedules (interval snapping, enabled/kill-switch
    gating) stay tested without arq.
  - Audit `test_trace_propagation.py`, `test_send_email_handler.py`,
    `test_registry.py`, `test_in_process_adapter*.py` — these exercise
    surviving code and STAY; drop only any arq-package import / arq-side
    assertion.
- **Migrations**: **none.** No table, column, index, or persisted state
  is touched. arq is a runtime Redis dispatch path with zero relational
  footprint; the `outbox_messages` table and its request-path writers
  are **unchanged** — only the runtime that drains it is removed.
  (`AppSettings.model_config` uses `extra="ignore"` — confirmed — so any
  stale `APP_JOBS_REDIS_URL` / `APP_JOBS_QUEUE_NAME` env var in a
  deployed environment is silently ignored; no compatibility shim.)
- **Docs** (arq/worker-runtime lines only — no wholesale rewrite; steps
  9/10/11 own that): `docs/background-jobs.md`, `docs/outbox.md`,
  `docs/operations.md`, `docs/observability.md`, `docs/architecture.md`,
  `docs/development.md`, `docs/email.md`, `README.md`, `CLAUDE.md`,
  `CONTRIBUTING.md` (line-by-line audit — the step-4 audit missed real
  `CONTRIBUTING.md` refs; this one is explicit).
- **Production behavior**: the jobs production validator refused
  `in_process` and accepted only `{arq}`; it now refuses `in_process`
  and accepts **no** job backend — production-with-deferred-work is not
  bootable until ROADMAP step 26 (`aws_sqs`) + step 27 (Lambda worker).
  The outbox production validator's `APP_OUTBOX_ENABLED=true` refusal is
  **unchanged** (Key decision 3). Any deployment running
  `APP_JOBS_BACKEND=arq` now fails fast at startup with "unknown
  backend" (intended — arq is gone). This is the honest mid-cleanup
  state of an AWS-first starter, not a silent regression; see "Key
  decision 2/3" for the rejected alternatives and why they are unsafe.
- **Quality gate**: `make quality` (lint + arch + typecheck) and
  `make test` MUST stay green after the removal. `make lint-arch` MUST
  show no new Import Linter violation (the new `CronSpec` module must
  not cross a feature boundary — the two per-feature `composition/worker.py`
  modules and `src/worker.py` may import it; verify it lives where the
  contracts allow). The job-queue contract suite MUST still pass for
  `in_process` and `fake`.

## Out of scope (do NOT touch)

- The `in_process` adapter
  (`src/features/background_jobs/adapters/outbound/in_process/`),
  `JobQueuePort`, `JobHandlerRegistry`, the `send_email` /
  `delete_user_assets` / `erase_user` handlers, and the handler/cron
  registry mechanism — they are the dev/test default and the surviving
  background-jobs concepts. Only the arq adapter + arq runtime go.
- The `aws_sqs` adapter, the `src/worker_lambda.py` Lambda runtime, and
  any AWS/SQS code or config — ROADMAP steps 26/27. Do not add an
  `sqs`/`aws_sqs` backend value, an SQS extra, an SQS accept-path to the
  validator, or revive the worker `CMD` to a real runtime here.
- The outbox→SNS/EventBridge cutover and any weakening of the
  `APP_OUTBOX_ENABLED=true` production refusal — ROADMAP step 28
  (and Key decision 3).
- The runtime `redis` dependency, the auth rate-limiter / principal-cache
  Redis wiring in `src/main.py`, and `fakeredis` — they are
  rate-limit/cache scope, not arq scope, and a production-safety
  regression if removed.
- The `arq + redis` Renovate co-version group and its
  `quality-automation` spec scenario — deferred to the AWS-SQS naming /
  doc-rewrite steps (flagged in the dependency audit).
- The `docs/operations.md` "production refuses to start if…" narrative
  reconciliation — ROADMAP step 11. Only delete arq/worker-runtime
  lines and state the minimal accurate post-removal reality.
- Any broader rewrite of `README.md` / `CLAUDE.md` beyond deleting
  arq/worker-runtime lines and restating the jobs row honestly —
  ROADMAP steps 9/10.
- ROADMAP sub-step 5b (the AWS SQS adapter + Lambda worker runtime) —
  a later step; 5a leaves a clean seam, it does not advance 5b.

This change is strictly ROADMAP ETAPA I step 5, sub-step 5a. It does not
advance step 5b (SQS/Lambda), steps 6–12 (SpiceDB/S3 removal, api.md,
README/CLAUDE/operations rewrites, cli docs), or any ETAPA II+ work.
