---
name: etapa1-adapter-removal
description: ROADMAP ETAPA I removes non-AWS production adapters one step per OpenSpec change; the production-validator must stay an honest refusal, not relax
metadata:
  type: project
---

ROADMAP ETAPA I (steps 3–7) removes non-AWS production-shaped adapters one at
a time, one OpenSpec change each: 3=SMTP (archived
`2026-05-16-remove-smtp-adapter`), 4=Resend (`remove-resend-adapter`),
5=arq, 6=SpiceDB stub, 7=S3 stub. Dev-only adapters (`console`, `in_process`,
`local`, `in_memory`) stay. Real AWS adapters arrive much later (SES at
step 25). Ports are kept (testability, not portability).

**Why:** AWS-first starter; "una sola opción opinada > tres opciones a
medias"; the ROADMAP norte is an honest repo mid-cleanup.

**How to apply (key recurring design call):** when an adapter removal makes a
backend `Literal` collapse to a single dev-only value, the production
validator that refuses that dev value MUST keep refusing it — do NOT relax it
so production boots. Rationale: the refusal exists so production never
silently uses a dev sink (e.g. `console` email black-holes mail). Removing
the last production backend makes production-with-that-feature intentionally
not bootable until the AWS adapter lands; that is the honest state, not a
regression. The ONLY forced code change is rewording the validator message to
stop naming the removed backend. This recurs for email (step 4) and will
recur for any future single-value collapse.

**Test ripple to always flag:** `src/app_platform/tests/test_settings.py`
has a shared `_VALID_PROD_ENV` baseline that prior steps repoint to whatever
backend is still production-valid. When no production-valid value remains,
repoint it to the dev value and isolate the now-always-present refusal in
every test that reuses the baseline to assert a *different* refusal.

Do NOT pre-empt later doc-rewrite steps: step 9=README, 10=CLAUDE,
11=`docs/operations.md` "production refuses to start if…" narrative. Adapter-
removal changes touch only the removed backend's lines + minimal honest
restatement. See [[openspec-convention]] for the MODIFY targets (email,
project-layout, quality-automation, authentication validator-surface).

**Step 5 (arq) is categorically bigger than 3/4 — it removes a RUNTIME, not
a port leaf.** `src/worker.py` IS arq (`run_worker`/`WorkerSettings`/`CronJob`);
the outbox relay + auth token-purge cron only run as arq crons; jobs AND
outbox prod validators both demand the runtime that's being deleted. Decision
taken in change `remove-arq-adapter`: **sub-split per ROADMAP line 18** — 5a
(this change) removes arq adapter+runtime, rewrites `src/worker.py` as a
runtime-agnostic composition-root + handler/cron-registry scaffold whose
`main()` exits non-zero "no runtime wired" (NOT deleted — step 27 needs the
seam; NOT left with dangling arq imports — won't typecheck), converts the two
per-feature `composition/worker.py` to runtime-agnostic `CronSpec` descriptors;
5b = ROADMAP step 26/27 (SQS adapter + Lambda worker). Keep BOTH prod refusals
(jobs `in_process`, outbox `APP_OUTBOX_ENABLED=true`) honest — same steps-3/4
stance. **Dependency trap:** the `worker` extra and `dev` group both carry arq
AND redis/fakeredis — remove ONLY arq; `redis` (auth rate-limiter + principal
cache) and `fakeredis` (surviving rate-limit tests) MUST stay. Leave the
`arq + redis` Renovate group + its quality-automation spec scenario UNTOUCHED
(pre-empts the SQS-naming decision; inert with arq absent) — flag the omission
explicitly. Delta targets for step 5: `background-jobs` (all 4 reqs MODIFIED),
`outbox` (Worker integration + trace-context MODIFIED), `project-layout`
(arq-result-retention REMOVED; graceful-shutdown / Dockerfile-worker-stage /
strategic-Any / Entrypoints MODIFIED), `quality-automation` (worker-extra split
MODIFIED), `authentication` (validator-surface MODIFIED). Pre-existing drift
spotted, NOT fixed (out of scope): the `Dockerfile exposes a dedicated worker
stage` req says `FROM runtime AS runtime-worker` but the actual Dockerfile uses
`FROM runtime-base AS runtime-worker` — the MODIFIED delta avoided re-asserting
the wrong base clause.
