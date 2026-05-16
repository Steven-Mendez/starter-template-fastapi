## 1. README.md — tagline / intro reframed AWS-first

- [x] 1.1 Rewrite the intro (~lines 3–7). Replace "production-shaped starter
      for FastAPI services … bundles the four pieces of infrastructure every
      real backend needs …" with an AWS-first framing in English, accurate to
      the CURRENT state: an AWS-first FastAPI starter; local dev needs no
      infrastructure beyond a Postgres container; production targets AWS; one
      opinionated option over several half-built ones (paraphrase
      `ROADMAP.md:3` in English — do NOT paste the Spanish verbatim).
- [x] 1.2 Name Cognito / SES / SQS / S3 / RDS / ElastiCache only as the
      project's production **direction at later roadmap steps**, reusing the
      existing "the production X arrives at a later roadmap step" phrasing
      pattern already used by the `email` / `background_jobs` rows. Do NOT
      claim any AWS adapter, endpoint, or config exists in the code today.
- [x] 1.3 Keep the step-1-authored "clone, run, then build your first
      feature from scratch following the documented hexagonal layout"
      sentence (~lines 9–13) substantively intact. It may be lightly
      re-sequenced to read after the new lede, but its build-from-scratch
      meaning MUST NOT change and NO scaffold-recovery prose may be
      reintroduced.

## 2. README.md — "What's New" section trimmed and de-linked

- [x] 2.1 Rewrite or remove the "What's New" section (~lines 15–22). It MUST
      NOT retain the broken `openspec/changes/starter-template-foundation/`
      link (the change is archived at
      `openspec/changes/archive/2026-05-13-starter-template-foundation/`) and
      MUST NOT imply repo history stops at `starter-template-foundation`.
- [x] 2.2 If kept, reduce it to one honest sentence pointing readers at
      `ROADMAP.md` for direction and `openspec/changes/archive/` for change
      history. Do NOT turn it into a per-change changelog.

## 3. README.md — Feature Inventory made seven-feature accurate

- [x] 3.1 Fix `README.md:53`. Replace
      `` | `file_storage` | `FileStoragePort` plus `local` adapter and `s3`
      stub. | `` with a row describing `FileStoragePort` plus a `local`
      adapter (dev/test) and a **real `boto3`-backed `s3` adapter** selected
      with `APP_STORAGE_BACKEND=s3`. The words "stub" / `NotImplementedError`
      / "placeholder" MUST NOT appear for the S3 adapter (discharges ROADMAP
      step 7's deferred README propagation; satisfies the canonical
      `project-layout` S3 scenario).
- [x] 3.2 Add an `outbox` row to the Feature Inventory: `OutboxPort`, the
      `outbox_messages` table, `SessionSQLModelOutboxAdapter`, and the
      `DispatchPending` relay that runs in the worker. Phrase it to match the
      canonical CLAUDE.md / `docs/architecture.md` description.
- [x] 3.3 Confirm the `email` row (`console` only; production email via AWS
      SES at a later roadmap step) and the `background_jobs` row
      (`in_process` only; production AWS SQS + a Lambda worker at a later
      roadmap step; runtime-agnostic worker scaffold) are accurate
      post-cleanup — keep them, only adjusting phrasing for consistency. Do
      NOT add SMTP/Resend/arq/SpiceDB rows (they were never adapter-level
      matrix rows and the adapters were removed in steps 1/3–6).

## 4. README.md — Project Structure tree

- [x] 4.1 Add the missing `outbox/` feature directory to the
      `src/features/` block of the Project Structure tree (~lines 89–95) so
      it matches the seven-feature source tree and stops contradicting the
      Feature Inventory.
- [x] 4.2 Align the `worker.py` tree comment with the
      runtime-agnostic-scaffold reality already stated elsewhere in the
      README (builds, logs handlers/cron descriptors, exits non-zero; no job
      runtime wired until a later roadmap step).
- [x] 4.3 Do NOT undertake a broader `src/platform/` → `src/app_platform/`
      tree re-derivation — the `src.`-prefix prose rule is governed by step
      1's already-satisfied `project-layout` scenario and a full tree rewrite
      is out of this step's brief. Limit tree edits to 4.1 and 4.2.

## 5. README.md — guard the already-satisfied step-1 criterion

- [x] 5.1 Verify (do NOT rewrite) that the build-from-scratch guidance in
      the intro and the "Starting A New Project" section is intact and that
      the tagline edit reintroduced NO scaffold-recovery prose. This
      criterion ("remove the recoverable-scaffold mention") is already
      satisfied by ROADMAP step 1 (`remove-template-scaffold-docs`); this
      step only guards it.

## 6. README.md — audit

- [x] 6.1 Grep `README.md` for `SMTP`, `Resend`, `arq`, `SpiceDB`/`spicedb`,
      `mailpit`, `_template`, `feature-template`, `recover the scaffold`,
      `recoverable`, `pre-removal`, and `s3 stub` / `NotImplementedError`.
      Confirm zero removed-adapter, scaffold-recovery, or S3-stub references.
      The only acceptable "template" hits are the project name
      `starter-template-fastapi` and unrelated prose.
- [x] 6.2 Confirm `KANBAN_SKIP_TESTCONTAINERS` (line ~323) is left exactly
      as-is — it is a real pre-existing testcontainers skip-flag env-var
      name, not a Kanban feature; renaming it is a code change and out of
      scope for this documentation step.
- [x] 6.3 Confirm no `src/cli/` command-reference section was added to
      `README.md` (that is ROADMAP step 12, explicitly out of scope here).

## 7. Wrap-up

- [x] 7.1 Confirm `git status` shows only `README.md` plus the OpenSpec
      change directory (`openspec/changes/readme-aws-first/`). No source,
      settings, env var, migration, test, `CLAUDE.md`, `docs/*.md`,
      `ROADMAP.md`, `pyproject.toml`, or `docker-compose.yml` change.
- [x] 7.2 Reconcile the verbatim "Documentation reflects the new layout"
      restatement in `specs/project-layout/spec.md` against the CANONICAL
      `openspec/specs/project-layout/spec.md` block. ROADMAP step 7
      (`fix-s3-stub-drift`) is in flight on the same requirement — if it
      archived first and further amended the block, re-copy the then-current
      canonical text so the restatement still byte-matches and no prior
      refinement (src.-prefix, scaffold-recovery, api.md, S3-stub) is
      dropped.
- [x] 7.3 Run `openspec validate readme-aws-first --strict` and confirm it
      passes.
- [x] 7.4 Confirm the rewritten `README.md` satisfies the new
      `project-layout` → "Documentation reflects the new layout" scenario
      ("README presents the AWS-first framing and a code-true feature
      inventory") and still satisfies the four pre-existing scenarios.
- [x] 7.5 Archive with `openspec archive readme-aws-first` (do NOT pass
      `--skip-specs` — this change carries a `project-layout` spec delta;
      see the SPEC-DELTA DECISION note in the proposal).
