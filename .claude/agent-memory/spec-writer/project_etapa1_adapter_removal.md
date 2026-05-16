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
11=`docs/operations.md` "production refuses to start if…" narrative,
12=`src/cli/` docs in README+CLAUDE. Adapter-removal changes touch only the
removed backend's lines + minimal honest restatement. See
[[openspec-convention]] for the MODIFY targets (email, project-layout,
quality-automation, authentication validator-surface).

**Step 9 (README AWS-first) — change `readme-aws-first`, drafted 2026-05-16.**
ONLY `README.md` + OpenSpec artifacts. Audited reality: scaffold-recovery
mention ALREADY removed by step 1 (zero `_template`/`recoverable` hits in
README) — step 9 only VERIFIES + guards it, does NOT fabricate work. The
ONLY false adapter claim is `README.md:53` "`s3` stub" (step 7's deferred
README propagation — fix to "real `boto3` `s3` adapter"). No
SMTP/Resend/arq/SpiceDB rows ever existed in the matrix (it was never
adapter-level). Two extra stale claims found beyond the brief: README omits
the `outbox` feature entirely (lists 6, code ships 7) in both Feature
Inventory AND Project Structure tree, and "four pieces of infrastructure"
intro framing pre-dates `outbox`+AWS-first; and the "What's New" section
links the now-broken `openspec/changes/starter-template-foundation/` (404 —
archived to `archive/2026-05-13-...`). Deferred-found (NOT fixed, flagged):
the `src/platform/`→`src/app_platform/` tree label (governed by step 1's
already-satisfied scenario) and the "run at least one worker per Redis
deployment" Deployment-Notes line (closer to step 11). Single delta target:
`project-layout` MODIFY `Documentation reflects the new layout` — restate
VERBATIM (now 5 paragraphs + 5 scenarios after step 7 folded in the
S3-adapter paragraph at canonical spec.md:99 + S3 scenario at :130-136), ADD
one scenario "README presents the AWS-first framing and a code-true feature
inventory". **Reconciliation hazard:** step 7 (`fix-s3-stub-drift`) is
in-flight on the SAME requirement — archive step MUST re-copy the canonical
block at archive time if step 7 lands first. Archive WITHOUT `--skip-specs`.

**Step 10 (CLAUDE.md AWS-first) — change `claude-md-reframe`, drafted
2026-05-16.** ONLY `CLAUDE.md` + OpenSpec artifacts. CLAUDE.md was ALREADY
partially correct (steps 1–7 edited incrementally). Audit found EXACTLY two
false statements, no third: (1) `CLAUDE.md:50` "Six features ship out of the
box" — WRONG, its own matrix at :53–61 lists 7 incl. `outbox` and
`ls src/features/` = 7; fix "Six"→"Seven", change nothing else in the
sentence. (2) `CLAUDE.md:164` "`adapters/outbound/s3/` — stub; raises
`NotImplementedError`" — step 7's deferred CLAUDE propagation; fix to real
`boto3` adapter via `APP_STORAGE_BACKEND=s3` (consistent w/ :60, canonical
spec.md:99). EVERYTHING ELSE verified correct, NOT churned: matrix rows
55–61 (console-only/SES-later, in_process-only/SQS-later, SpiceDB-free,
"local + S3 (`boto3`)", outbox row present), "Adding a new feature" 196–207
(from-scratch, zero `_template`/recovery residue — step 1 done), production
checklist 230–247 + env tables 249–278 (audited against all 4 infra
`validate_production` validators — email refuses console, jobs refuses
in_process, file_storage refuses local when STORAGE_ENABLED, outbox must be
enabled — all match), the two `arq` refs 157/222 (accurately say "removed in
step 5"). Zero SMTP/Resend/SpiceDB/mailpit hits. Single delta target:
`project-layout` MODIFY `Documentation reflects the new layout` — restate
VERBATIM (NOW 4 SHALL paragraphs + 6 scenarios: step 7 folded S3 paragraph
at canonical spec.md:99 + S3 scenario :130, step 9 folded README AWS-first
scenario :137), ADD one scenario "CLAUDE.md presents a code-true
seven-feature inventory with no stale-adapter claims". **Reconciliation
hazard:** step 7 (`fix-s3-stub-drift`) change dir still exists (in flight on
SAME requirement) — archiver MUST re-copy canonical block at archive time.
Archive WITHOUT `--skip-specs`. Step 12 (`src/cli/` docs) explicitly
deferred — NO cli section added.

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

**Step 7 (S3) — DECIDED 2026-05-16: Option A, drift-fix NOT deletion. The
ROADMAP/brief premise is FALSE.** ROADMAP.md:48 + briefs call S3 a "stub
raising `NotImplementedError`" mirroring SpiceDB. WRONG against code:
`S3FileStorageAdapter` is a fully real, contract-tested `boto3` adapter (real
put/get/delete/list/signed_url, moto-mocked 3-way contract `[fake,local,s3]`,
8-test `test_s3_adapter.py`). Canonical `openspec/specs/file-storage/spec.md`
even has a req literally named `S3 adapter is a real boto3 implementation`
("SHALL NOT raise NotImplementedError"). **The repo owner chose Option A: the
real adapter STAYS (it is exactly what ROADMAP step 24 wants; S3 is NOT on the
SMTP/Resend/arq/SpiceDB remove-list).** Step 7 is wording-only: correct the
false "stub"/`NotImplementedError`/"placeholder" prose so docs match code, and
fix the false ROADMAP line-48 text + checkbox.

**This SUPERSEDES the earlier pre-planned deletion approach** (collapse the
`StorageBackend` `Literal`, drop the `s3` extra/`moto`, reword validator,
`_VALID_PROD_ENV` analysis, REMOVE `S3 adapter is a real boto3 implementation`,
etc.) — that plan is NOT executed. No code/test/extra/setting/`Literal`/
migration change. Steps-3/4 precedent does NOT apply here: S3 *is* the AWS
backend, there is no non-AWS production backend to remove.

Wording sites to correct (verified): `src/features/file_storage/__init__.py:4`
("`s3` as a stub for production"), `docs/architecture.md:36` (feature row
"local adapter, S3 stub"), `docs/architecture.md:245` (Design-Decisions "S3
stub" row — REWRITE both cells to a code-true decision, e.g. provider-agnostic
`AWS_ENDPOINT_URL_S3`; do NOT delete the row), `docs/architecture.md:251`
(Tradeoffs "is a stub" bullet — reframe as operational prerequisite, keep the
bullet). `docs/file-storage.md` is ALREADY accurate — audited, NO edit (its
line-5 "ships as scaffolding" = unwired feature, accurate). `README.md:53` +
`CLAUDE.md:164` carry the same false wording but are DEFERRED to ROADMAP
steps 9/10 (whole-file rewrites) — proposal carries a propagation note that
9/10 MUST land "real boto3 adapter". `ROADMAP.md:121` (step-24 sub-bullet) NOT
edited (step 24's change owns it). Single delta target: `project-layout` MODIFY
`Documentation reflects the new layout` — restate verbatim, NARROW the S3
"ships as scaffolding **stub**" carve-out to drop the word that blesses "stub",
add one scenario "no doc calls the real S3 adapter a stub", carry the
`src.`-prefix / scaffold-recovery / `docs/api.md` scenarios forward. The
`file-storage` capability is NOT touched (its "S3 adapter is a real boto3
implementation" req is already correct — it is the spec-level proof the premise
was false). Archive WITHOUT `--skip-specs`. Change: `fix-s3-stub-drift`
(NOT `remove-s3-stub`).

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
