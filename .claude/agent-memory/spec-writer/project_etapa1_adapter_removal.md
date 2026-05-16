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

**Step 6 (SpiceDB stub) is categorically SMALLER than 3/4/5 — pure dead-code
deletion, NO production-validator involvement.** Unlike email/jobs backends,
there is NO authz backend selector setting, NO env var, NO `Literal`, NO
`validate_production` arm naming SpiceDB anywhere. `build_authorization_container`
constructs only `SQLModelAuthorizationAdapter`; the stub is imported by nothing
but its own `__init__.py`. So the "keep the prod refusal honest" stance does
NOT apply here — no validator wording change, no `_VALID_PROD_ENV` repoint, no
migration. `CONTRIBUTING.md` and `pyproject.toml` have ZERO SpiceDB refs
(verified); `src/**/tests/` has ZERO SpiceDB refs (no stub test to delete).
Delta target: `authorization` capability only — REMOVE `SpiceDB adapter is a
structural placeholder`; MODIFY `AuthorizationPort defines the application-side
authorization contract` (Two-adapters scenario → single SQLModel-adapter
scenario), `Authorization is a self-contained feature slice` (drop ", the
SpiceDB stub" from SHALL text), `Authorization config is registered
programmatically per feature` (drop "(SpiceDB, OpenFGA)" from SHALL text).
Reword docstrings to be backend-neutral (port stays the swap boundary; just
stop naming a deleted stub + the out-of-scope SpiceDB/AuthZed vendor list).
AVP/Cedar is ROADMAP step 53 — out of scope. Change: `remove-spicedb-stub`.

**Step 7 (S3) — the ROADMAP/brief premise is FALSE; it is steps-3/4-class,
NOT step-6-class.** ROADMAP.md:48 + briefs call S3 a "stub raising
`NotImplementedError`" mirroring SpiceDB. WRONG against code: `S3FileStorageAdapter`
is a fully real, contract-tested `boto3` adapter (real put/get/delete/list/
signed_url, moto-mocked 3-way contract `[fake,local,s3]`, 8-test
`test_s3_adapter.py`). Canonical `openspec/specs/file-storage/spec.md` even has
a req literally named `S3 adapter is a real boto3 implementation` ("SHALL NOT
raise NotImplementedError"). So apply the steps-3/4 precedent: collapse
`StorageBackend`/`storage_backend` `Literal["local","s3"]`→`["local"]`, keep
the prod validator refusing `local`-when-`APP_STORAGE_ENABLED=true`, reword
message to drop `s3`/`APP_STORAGE_S3_BUCKET` BUT KEEP the literal substring
`APP_STORAGE_BACKEND` (the shared-baseline test asserts `match="APP_STORAGE_BACKEND"`).
Real deps go: `s3=["boto3~=1.34"]` extra + dev-group `boto3~=1.34`/`moto~=5.0`/
`boto3-stubs[s3]`; `uv lock`. **No `boto3` Import Linter `forbidden_modules`
entry exists** (unlike step-4 httpx) — nothing to preserve there.
**`_VALID_PROD_ENV` sets NO `APP_STORAGE_*`** → storage is disabled in baseline
→ storage refusal is NOT always-present → `_assert_only_always_present_refusals`
stays at TWO entries (email+jobs), NOT three; `src/app_platform/tests/test_settings.py`
needs NO edit (`test_production_rejects_local_storage_enabled` already opts in
and resolves via the retained `APP_STORAGE_BACKEND` substring). `CONTRIBUTING.md`
+ `docs/background-jobs.md` audited: ZERO real S3 refs (no edit). In-tree drift
to fix while removing: `docs/architecture.md:245/251` + `src/features/file_storage/__init__.py`
falsely call the real adapter a "stub". Delta targets: `file-storage` (REMOVE
`S3 adapter is a real boto3 implementation`; MODIFY `FileStoragePort contract`,
`Local adapter remains the development default`, `Settings select the active
adapter`, `Adapters are isolated from inbound layers`), `project-layout`
(REMOVE `S3 adapter is configured for FastAPI concurrency`; MODIFY
`Documentation reflects the new layout` — its S3-"scaffolding" carve-out),
`quality-automation` (MODIFY `Runtime dependencies are split into core, api,
worker, and adapter extras` + `Integration markers reflect real-backend usage`),
`authentication` (MODIFY validator-surface req). Keep Renovate `boto3+botocore`
group + its quality-automation scenario UNTOUCHED (inert; pre-empts AWS-S3
naming) — flag the omission. Real `aws_s3` adapter = later roadmap step (NOT
step 23: 23=SecretsPort, 24=aws_s3; phrase as "a later roadmap step", don't
hard-code). Change: `remove-s3-stub`.

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
