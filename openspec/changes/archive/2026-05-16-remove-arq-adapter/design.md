# Design — remove-arq-adapter (ROADMAP ETAPA I step 5, sub-step 5a)

## Context

Steps 3 (SMTP) and 4 (Resend) each removed a non-AWS, production-shaped
*dispatch leaf* behind a port: an `EmailPort` adapter that did one
thing (send an email over a wire) and had zero structural pull on the
rest of the system. The established precedent from those changes (memory
`etapa1-adapter-removal`, the archived proposals): when an adapter
removal collapses a backend `Literal` to a single dev-only value, the
production validator that refuses that dev value **keeps refusing it** —
production-with-that-capability is intentionally not bootable until the
AWS adapter lands; that is the honest state, not a regression. The only
forced code change is rewording the validator message to stop naming the
removed backend.

`arq` is categorically different from SMTP/Resend. It is not a leaf
behind a port — it is the **worker process runtime itself**. Three
load-bearing facts:

1. `src/worker.py` *is* `arq`: `from arq import run_worker`,
   `arq.connections.RedisSettings`, `arq.cron.CronJob`,
   `arq.worker.Function`, `arq.typing.StartupShutdown`/`WorkerCoroutine`,
   plus an `on_shutdown` hook that drains an in-flight outbox-relay tick
   and disposes the SQLAlchemy engine + Redis pool. 399 lines, almost
   all of it composition that the *web* process also needs.
2. The **outbox relay** (`DispatchPending`) and the **auth token-purge
   cron** (`PurgeExpiredTokens`) only ever run as `arq` cron jobs.
   `src/features/outbox/composition/worker.py` and
   `src/features/authentication/composition/worker.py` both
   `from arq.cron import CronJob, cron` and return `arq` `CronJob`s.
3. The production validators *demand* both of those run in production
   (`APP_JOBS_BACKEND != in_process` and `APP_OUTBOX_ENABLED=true`), yet
   the only thing that can run them is the arq runtime being removed.

So removing arq is not "delete an adapter and reword one message". It
forces three architectural decisions (the proposal's Key decisions 1–3)
and is materially larger than steps 3–4. This document records the
sub-split decision, the three resolutions, the dependency audit, the
contract-test reshape, the spec-delta targeting, and the alternatives
considered and rejected.

## Sub-split decision

ROADMAP rule (line 18): "*Si un paso resulta más grande de lo esperado,
lo partimos en sub-pasos pero seguimos en orden.*" This step qualifies.
The question is **where to cut**, not whether.

### Options for the cut

- **A — one monolithic change**: remove arq adapter + runtime + the SQS
  adapter + the Lambda worker, all at once. **Rejected.** The SQS
  adapter is ROADMAP step 26 and the Lambda worker is step 27 — both
  many steps away, gated by ETAPA V "SecretsPort first, S3 before
  SES/SQS". Pulling them into step 5 violates strict ROADMAP order and
  the constraint "do NOT add SQS/Lambda/AWS".
- **B — split off the dependency/renovate hygiene as a separate
  sub-step, leave it for later**: do the code/runtime collapse in 5a,
  defer the `pyproject.toml`/`uv.lock`/renovate edits to 5b.
  **Rejected** for `pyproject.toml`/`uv.lock`: leaving a
  `worker = ["arq~=0.26"]` extra and an `arq~=0.26` dev dep after
  deleting every arq import is *exactly* the dead-config dishonesty
  ETAPA I exists to remove, and step 4 set the precedent of removing the
  `resend` extra in the same change as the adapter. **Accepted** only
  for the `arq + redis` *renovate co-version group*: that is a
  forward-looking grouping whose clean reconciliation depends on the
  not-yet-made AWS-SQS naming decision; it is inert with arq absent;
  touching it now pre-empts step 26. So it is deferred and explicitly
  flagged, not silently skipped.
- **C — split at the arq/AWS boundary (CHOSEN)**: 5a removes the arq
  adapter + arq runtime and everything it forces for code/test/doc/spec
  coherence, leaving a runtime-agnostic seam; 5b is ROADMAP step 26/27
  (the AWS SQS adapter + Lambda worker), a later step that re-attaches a
  real runtime to the seam 5a leaves.

### The chosen ordered sub-steps

- **5a (THIS change)** — *Remove the arq adapter and arq runtime;
  collapse `jobs_backend` to `in_process`; convert `src/worker.py` and
  the two per-feature `composition/worker.py` cron modules to a
  runtime-agnostic composition-root + handler/cron-registry scaffold
  (no `arq` import anywhere); narrow settings; keep every
  production-safety refusal honest (jobs + outbox); update
  tests/docs/spec deltas.* Coherent and shippable alone: `make quality`
  + `make test` green, zero arq symbols, the shared composition root +
  handler/cron registry preserved.
- **5b (NOT this change; = ROADMAP step 26/27)** — *Add the `aws_sqs`
  `JobQueuePort` adapter and the `src/worker_lambda.py` Lambda runtime;
  re-attach the relay/purge cron descriptors to a real scheduler; add
  the SQS accept-path to the jobs validator.* Out of scope here; 5a only
  leaves the seam.

### Why 5a is internally coherent (and not arbitrarily truncated)

A sub-step must be a self-consistent end state, not a half-applied
refactor. 5a is: after it, `APP_JOBS_BACKEND` accepts exactly one value
(`in_process`), the production validators refuse it honestly (same
posture as steps 3/4), no module imports `arq`, the worker scaffold and
both cron modules type-check and are unit-tested, and the only thing
"missing" is a production runtime that the ROADMAP *explicitly schedules
for a later step*. That is precisely the steps-3/4 honest-mid-cleanup
shape, just one layer up (a runtime instead of a dispatch leaf). It does
not strand 5b: the composition root, the handler registry, and the cron
descriptors are all preserved, so step 27's `src/worker_lambda.py`
("misma raíz de composición que `src/main.py` y `src/worker.py`") has an
intact `src/worker.py` to mirror.

## Key decision 1 — fate of `src/worker.py`

Three options, against the four constraints in the brief (a: removes arq
fully, b: preserves the shared composition root + handler/cron registry,
c: no dead arq imports, d: `make quality`/`make test` green):

| Option | a | b | c | d | Verdict |
|---|---|---|---|---|---|
| Delete `src/worker.py` entirely | ✅ | ❌ loses the composition root step 27 must mirror | ✅ | ✅ | **Rejected** — strands ROADMAP step 27 ("misma raíz que `src/worker.py`"); deletes ~250 lines of non-arq composition the future runtime needs. |
| Keep `src/worker.py`, only strip the `arq` *imports* | ❌ leaves `WorkerSettings`/`run_worker`/`CronJob` refs dangling | ✅ | ❌ | ❌ won't type-check | **Rejected** — not a real end state. |
| Reduce to a runtime-agnostic composition-root + handler/cron-registry scaffold | ✅ | ✅ | ✅ | ✅ | **CHOSEN** |

**Chosen shape of the rewritten `src/worker.py`:**

- Keeps: `get_settings()`, `configure_logging(...)`, building the
  email/jobs/outbox/users/file-storage containers, registering
  `send_email` / `delete_user_assets` / `erase_user` handlers with their
  outbox-backed dedupe, sealing the registry, and collecting the relay +
  auth-purge cron *descriptors* (now `CronSpec`, see below). The
  engine/Redis construction and the `_on_shutdown` *body* (engine
  dispose, redis close, tracing flush) are kept as plain reusable
  helpers — they are the drain logic step 27's runtime re-binds; only
  the *arq binding* of them goes.
- Removes: every `import arq...`, the `WorkerSettings` class,
  `build_arq_functions(...)`, `RedisSettings.from_dsn(...)`,
  `_wrap_relay_tick` + the `cron_job.coroutine = cast(...)` arq-typing
  dance, and `run_worker(...)`.
- `main()`: builds the scaffold (so composition errors still surface as
  a loud failure, exactly as today), logs the registered handlers and
  collected cron descriptors, then **exits non-zero** with a clear
  message: *"No background-job runtime is wired. `arq` was removed in
  ROADMAP ETAPA I step 5; the production worker runtime (AWS SQS +
  Lambda) arrives at ROADMAP steps 26–27. `make worker` will not process
  jobs until then."* This mirrors the production-validator stance:
  honest loud refusal, never a silent no-op that looks healthy.

This satisfies all four constraints and leaves step 27 a minimal job:
add `src/worker_lambda.py`, bind the preserved registry + cron
descriptors to the SQS/Lambda event loop.

## Cron coherence — the `CronSpec` descriptor

The two per-feature cron modules currently return `arq.cron.CronJob`
objects. To remove arq without losing the *schedule declarations* (and
their unit tests for interval-snapping and the kill-switch / enabled
gating), introduce a tiny runtime-agnostic descriptor owned by the
background-jobs feature:

```
@dataclass(frozen=True, slots=True)
class CronSpec:
    name: str
    interval_seconds: int          # already snapped to a divisor of 60
    run_at_startup: bool
    callable: Callable[[], None]   # the sync tick; no ctx, no arq
```

- `src/features/outbox/composition/worker.py` →
  `build_relay_cron_specs(container) -> Sequence[CronSpec]` (returns
  `[]` when `APP_OUTBOX_ENABLED=false`, exactly as today; the
  `_snap_to_divisor` + `outbox-relay`/`outbox-prune` logic is carried
  forward verbatim, only the `cron(...)` wrapping is replaced).
- `src/features/authentication/composition/worker.py` →
  `build_auth_maintenance_cron_specs(...) -> Sequence[CronSpec]` (returns
  `[]` when `interval_minutes <= 0` — the kill switch — exactly as
  today).

**Import Linter placement (must verify with `make lint-arch`):** both
per-feature `composition/worker.py` modules and `src/worker.py` need to
import `CronSpec`. The brief's CLAUDE.md says
`email`/`background_jobs`/`file_storage` have no feature imports and that
`worker.py` "is permitted to import every feature's composition" (the
explicit pyproject exception around line 657). `CronSpec` is a
background-jobs *concept*, so it belongs under
`src/features/background_jobs/`. Placing it at
`src/features/background_jobs/application/cron.py` keeps it in the
application layer (no framework imports) and lets the worker scaffold
import it; the `outbox`/`authentication` `composition/worker.py` modules
importing a `background_jobs.application` symbol must be checked against
the contracts (`background_jobs ↛ other features` is one-directional —
other features importing *from* background_jobs is a different edge;
confirm it is allowed, and if a contract forbids it, fall back to
defining `CronSpec` in a platform-neutral location the implementer
selects — this is an implementation latitude explicitly called out so
the implementer resolves it against `make lint-arch`, not by guessing).

## Key decision 2 — jobs production validator stays a refusal

Identical reasoning to step 4's email decision (memory
`etapa1-adapter-removal`). The jobs validator
(`background_jobs/composition/settings.py:86-91`) currently appends an
error when `backend == "in_process"` in production. After arq removal
`in_process` is the only value.

**Keep the refusal.** The in-process adapter runs "deferred" work
*inline in the request thread* and *loses every queued job on restart*
(its own docstring says so). Relaxing the refusal so production boots on
`in_process` would make a production deploy come up green while
`send_email` / `delete_user_assets` / `erase_user` execute synchronously
in the request path and the outbox relay never runs. A loud boot failure
is strictly safer. The only forced change is the message: it currently
names `'arq'` and `APP_JOBS_REDIS_URL`; reword to state no production job
backend exists yet (AWS SQS at a later roadmap step). Rejected
alternative: relax to allow `in_process` in prod — rejected for the
exact reason step 4 rejected the `console` analogue (silent production
degradation replacing a loud "not ready").

## Key decision 3 — the outbox-relay coherence resolution

This is the decision with no SMTP/Resend precedent, so it is argued in
full.

**The tension:** `OutboxSettings.validate_production` refuses startup
when `APP_OUTBOX_ENABLED=false` in production
(`openspec/specs/outbox/spec.md` "Per-feature settings projection and
production validator"). Request-path consumers in `authentication` write
to the outbox *unconditionally* ("Authentication request-path consumers
go through the outbox"). The relay (`DispatchPending`) drains those rows
and only ever ran inside the arq worker. Remove the arq runtime and
production simultaneously (a) demands `APP_OUTBOX_ENABLED=true`, (b)
has nothing that can run the relay until ROADMAP step 26/27. Production
is therefore not bootable-into-a-working-state for deferred work.

**Options weighed:**

1. **Keep both refusals (jobs + outbox) unchanged; production simply not
   bootable for deferred work until step 26/27.** Fully consistent with
   the steps-3/4 "honest over convenient" precedent. Minimal blast
   radius. No safety invariant weakened. Does not pre-empt step 11 or
   28. **CHOSEN.**
2. Flip the `APP_OUTBOX_ENABLED=true` production refusal to a *warning*
   so production "boots again". **Rejected** — this silently weakens a
   production-safety invariant: with the refusal gone, a production
   deploy with `APP_OUTBOX_ENABLED=true` (the required value) and no
   running relay would write outbox rows that are *never delivered*
   (password-reset / email-verify / GDPR-erase side effects silently
   stranded), and a deploy with `APP_OUTBOX_ENABLED=false` would now be
   *accepted*, dropping the request-path writes' durability guarantee
   entirely. It also pre-empts ROADMAP step 28 (outbox→bus) and step 11
   (operations.md narrative), both explicitly out of scope.
3. Disable the request-path outbox writes so nothing accumulates.
   **Rejected** — that is a behavioral change to `authentication`,
   wildly out of scope, and reverses an architectural decision
   (transactional outbox) the ROADMAP does not revisit until step 28.

**Resolution (option 1):** the `APP_OUTBOX_ENABLED=true` production
refusal is **unchanged**. The spec delta for the outbox `Worker
integration` requirement is restated to say the worker *scaffold*
collects the relay cron descriptor when enabled and the *real scheduler*
arrives at a later roadmap step, the web process still never runs the
relay, and the `APP_OUTBOX_ENABLED=true` production refusal is unchanged.
The minimal accurate post-step-5 reality, stated in the narrowly-scoped
doc edits: *production with deferred work is intentionally not bootable
until AWS SQS (step 26) + the Lambda worker (step 27); the
`outbox_messages` table and its request-path writers are unchanged —
only the runtime that drains it is removed.* This is the same shape as
decisions 1 and 2: an honest "not ready until the AWS step", never a
silent weakening.

## Dependency audit (the careful `redis` part)

`pyproject.toml` references arq/worker/redis in these roles. Conclusions
(the implementer re-verifies each grep before editing):

1. **`worker = ["arq~=0.26", "redis~=...")` optional extra.**
   `arq` entry **removed**. `redis` entry **KEPT**. Reason:
   `src/main.py` and `src/features/background_jobs/composition/container.py`
   both `import redis as redis_lib`, and the *shared* Redis client is
   what backs the auth **distributed rate limiter** and the **principal
   cache** (CLAUDE.md production checklist: `APP_AUTH_REDIS_URL` "required
   for both the auth rate limiter and the principal cache"). Those are
   not jobs concerns and they survive. Removing `redis` would break
   distributed rate limiting + principal-cache invalidation in
   multi-replica deploys — a production-safety regression and out of
   scope. The extra key (`worker`) is kept as-is with a comment that arq
   was removed and the real runtime arrives at step 26/27; *renaming*
   the extra is cosmetic, couples to the renovate-group decision, and is
   deferred.
2. **`dev` group `"arq~=0.26"`** — **removed** (only the arq adapter and
   its tests imported it). **`fakeredis`** in `dev` — **KEPT**: grep
   shows `fakeredis` is imported by the job-queue contract test (the arq
   factory — removed here) **and** by surviving auth rate-limiter /
   principal-cache tests that exercise the Redis path. Removing it
   breaks those. Only the arq factory's use of it goes.
3. **`arq` + `redis` Renovate co-version group** (in `renovate.json`,
   asserted by the `quality-automation` spec "Co-versioned package
   groups are declared" scenario). **KEPT UNTOUCHED, EXPLICITLY
   FLAGGED.** Editing it (a) pre-empts the AWS-SQS naming decision
   (ROADMAP step 26 — what replaces `arq` in the group?), (b) is a
   dependency-grouping concern better reconciled with steps 9/10/11 or
   step 26, (c) is inert with arq absent (Renovate finds no `arq` to
   bump; `redis` still groups fine alone). Not modifying the
   `quality-automation` "Co-versioned package groups" requirement is a
   deliberate, audited omission — recorded here so a reviewer does not
   read it as a miss.
4. **Runtime `redis` dependency / any `redis` Import Linter
   `forbidden_modules` guardrail / the rate-limit & principal-cache
   wiring in `src/main.py`** — **KEPT, UNTOUCHED.** Rate-limit/cache
   scope, not arq scope.
5. **`uv.lock`** — regenerated via `uv lock` after the `pyproject.toml`
   edits. Expectation: `arq` and arq-only transitives drop;
   `redis`/`fakeredis` and their transitives stay. Commit the
   regenerated lock.

## Contract-test reshape (the non-obvious test ripple)

`test_job_queue_port_contract.py` parametrises three factories
`[in_process, arq, fake]`. Two `enqueue_at` scenarios specifically rely
on the *scheduling-capable* adapters (`arq`, `fake`) because
`InProcessJobQueueAdapter.enqueue_at` raises `NotImplementedError` by
design (its docstring says "wire the arq adapter … for scheduled
behaviour" — that guidance is now stale and must be reworded in the
adapter docstring to not name arq).

Reshape:
- Drop `_arq_factory`, the `arq` id, and the
  `from ...arq import ArqJobQueueAdapter` + the `import fakeredis` used
  *only* by the arq factory (keep `import fakeredis` if any surviving
  factory needs it — it does not after the arq factory goes, so it is
  removed from this file specifically; `fakeredis` the *dependency*
  stays for the rate-limit/cache tests, see audit).
- `test_enqueue_succeeds_for_registered_job` /
  `test_enqueue_unknown_job_raises`: parametrise over
  `[in_process, fake]`.
- `test_enqueue_at_succeeds_for_registered_job_on_scheduling_adapters`:
  drop the arq line, keep the `_fake_factory` line (the fake is now the
  only shipped scheduling-capable surface; this is honest — there is no
  production scheduler until step 26).
- `test_enqueue_at_unknown_job_raises`: parametrise over `[fake]` only.
- `test_in_process_adapter_refuses_enqueue_at`: **kept verbatim** — it
  pins the surviving `in_process` surface (still the right contract).
- Reword the `InProcessJobQueueAdapter.enqueue_at` docstring so it no
  longer says "set APP_JOBS_BACKEND=arq for scheduled execution"
  (state: scheduled execution requires the production job runtime, which
  arrives at a later roadmap step).

## `_VALID_PROD_ENV` reconciliation (memory `etapa1-adapter-removal`)

`src/app_platform/tests/test_settings.py` has a shared `_VALID_PROD_ENV`
baseline that prior steps repointed to whatever backend stayed
production-valid. For jobs, **no production-valid value remains**
(`in_process` is the only value and it is always refused in production).
Per the memory's recorded ripple ("when no production-valid value
remains, repoint to the dev value and isolate the now-always-present
refusal"):

- Remove `APP_JOBS_BACKEND` and `APP_JOBS_REDIS_URL` from
  `_VALID_PROD_ENV` entirely. The settings default for `jobs_backend` is
  `in_process`, so omitting the key leaves the always-present
  jobs-backend refusal in any production env constructed from the
  baseline.
- Keep `APP_OUTBOX_ENABLED=true` in `_VALID_PROD_ENV` (Key decision 3 —
  the outbox prod requirement is unchanged; its refusal must NOT become
  always-present, so the baseline must keep satisfying it).
- Delete `test_arq_backend_requires_redis_url`.
- Keep/strengthen the `in_process`-refused-in-production test: assert
  `APP_ENVIRONMENT=production` (with the rest of a valid env) raises
  `ValidationError` whose message reports the jobs-backend problem and
  names no removed backend (no `arq`, no `APP_JOBS_REDIS_URL`).
- Every other `_VALID_PROD_ENV`-based production test that asserts a
  *different* refusal must isolate the now-always-present jobs-backend
  error from its assertion so it still targets its own env var (same
  technique step 4 used for the always-present email-backend error).

## Spec-delta targeting

Strict validation needs ≥1 delta op; MODIFIED/REMOVED requirement names
must match the existing `openspec/specs/<cap>/spec.md` headers verbatim,
and the body must restate the full SHALL text + carry existing scenarios
forward + ≥1 `#### Scenario:`. Exact targets:

| Capability (file) | Requirement (verbatim header) | Op |
|---|---|---|
| `background-jobs` | `Background-jobs is a self-contained feature slice` | MODIFIED — drop the `arq` adapter clause; only `in_process` enumerated |
| `background-jobs` | `Adapter selection by configuration with production guard` | MODIFIED — `APP_JOBS_BACKEND` accepts only `in_process`; production refuses it, no backend accepted; drop the "arq requires Redis URL" scenario |
| `background-jobs` | `Features register their job handlers at composition time` | MODIFIED — registry/sealing unchanged; restate without "the worker (arq)" phrasing |
| `background-jobs` | `A worker entrypoint is available` | MODIFIED — "a runtime-agnostic worker composition-root scaffold exists; the real runtime (AWS SQS/Lambda) arrives at a later roadmap step; `make worker` exits non-zero until then" |
| `outbox` | `Worker integration` | MODIFIED — scaffold collects the relay cron descriptor when `APP_OUTBOX_ENABLED=true`; real scheduler later; web never runs the relay; the `APP_OUTBOX_ENABLED=true` production refusal is unchanged |
| `outbox` | `Outbox carries W3C trace context end-to-end` | MODIFIED — "(both in-process and arq)" → "(the in-process entrypoint)"; carry the three scenarios forward |
| `project-layout` | `arq worker has bounded result retention with per-handler override` | REMOVED — wholly an arq-`WorkerSettings`/`keep_result` requirement; result retention is a SQS/Lambda concern (step 26) |
| `project-layout` | `Process shutdown is graceful and bounded` | MODIFIED — API lifespan drain unchanged; "the arq worker SHALL implement on_shutdown…" → "the future job runtime SHALL implement the equivalent drain"; carry scenarios |
| `project-layout` | `Dockerfile exposes a dedicated worker stage` | MODIFIED — stage + hardened base unchanged; "starts the arq worker" scenario → "runs the worker scaffold, which exits non-zero until the AWS SQS/Lambda runtime is wired" |
| `project-layout` | `Strategic ``Any``/``object`` hotspots are typed` | MODIFIED — drop the arq `WorkerSettings`/`CronJob` typing clause + its two scenarios; carry the `_principal_from_user` clause + scenario forward unchanged |
| `project-layout` | `Entrypoints reference modules by their real names` | MODIFIED — `worker` stays a real module; restate the Makefile scenario without "arq worker" phrasing |
| `quality-automation` | `Runtime dependencies are split into ``core``, ``api``, ``worker``, and adapter extras` | MODIFIED — `worker` extra lists `redis` (not `arq`); the "Worker role install brings arq and redis" scenario → "brings redis; no arq (the worker runtime arrives at a later roadmap step)" |
| `authentication` | `Every documented production refusal has a unit test` | MODIFIED — the jobs-backend refusal it implies is "no production job backend exists" (no accept-path test); carry the email + other clauses forward verbatim |

**Deliberately NOT modified (audited omissions, flagged):**

- `quality-automation` → `Renovate manages Python and GitHub Actions
  dependencies` ("Co-versioned package groups are declared", the
  `arq + redis` group). Kept because reconciling it pre-empts the
  AWS-SQS naming decision (step 26) and is a renovate-grouping concern;
  the group is inert with arq absent.
- `outbox` → `PruneOutbox is invocable as a one-shot CLI` and
  `Per-feature settings projection and production validator`. The CLI
  (`src/cli/outbox_prune.py`) is a standalone composition root with **no
  arq import** (verified) — unchanged. The outbox production validator
  is unchanged (Key decision 3) so its requirement text stays verbatim.
- The `in_process` adapter, `JobQueuePort`,
  `JobHandlerRegistry`, the `send_email`/`delete_user_assets`/`erase_user`
  handlers — surviving concepts, untouched.

## Risks and the quality gate

- **Import Linter**: the `CronSpec` placement is the only new
  cross-module edge. Must be resolved against `make lint-arch`, not
  guessed — flagged as implementer latitude with a safe fallback (a
  platform-neutral location) above.
- **`make typecheck`**: removing `WorkerSettings`/`CronJob` must leave
  no dangling annotation; the `project-layout` "Strategic Any" delta
  drops the now-unsatisfiable arq-typing scenarios so the spec and code
  stay consistent.
- **`make test`**: the contract de-parametrisation, the deleted arq
  tests, the rewritten graceful-shutdown test, and the `_VALID_PROD_ENV`
  reconciliation must land together so the suite stays green and the
  always-present jobs refusal is isolated everywhere it would otherwise
  mask another assertion.
- **No migrations** — verified: zero relational footprint; the
  `outbox_messages` table and its writers are untouched;
  `extra="ignore"` means stale `APP_JOBS_*` env vars are silently
  ignored, no shim.
