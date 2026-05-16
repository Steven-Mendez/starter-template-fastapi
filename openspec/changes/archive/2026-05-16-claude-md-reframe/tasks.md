# Tasks — claude-md-reframe (ROADMAP ETAPA I step 10)

## 1. Audit (verify the already-correct state — do NOT churn)

- [x] Confirm `src/features/` ships exactly seven feature packages:
      `authentication/ users/ authorization/ email/ background_jobs/
      file_storage/ outbox/` (`ls src/features/`).
- [x] Confirm `CLAUDE.md:53–61` already lists all seven matrix rows and that
      the `email` / `background_jobs` / `authorization` / `file_storage` /
      `outbox` rows are post-cleanup accurate (console-only/SES-later;
      in_process-only/SQS-later/runtime-agnostic scaffold; SpiceDB-free;
      "local + S3 (`boto3`) adapters"; `outbox` row present). Leave them
      unchanged.
- [x] Grep `CLAUDE.md` for `SMTP`/`smtp`, `Resend`/`resend`,
      `SpiceDB`/`spicedb`, `mailpit`, `_template`, `feature-template`,
      `recover the scaffold`, `recoverable`, `pre-removal` — confirm **zero**
      hits (already purged by steps 1, 3–6). Do not fabricate work here.
- [x] Confirm the two `arq` references (`CLAUDE.md:157`, `:222`) already
      describe `arq` as removed in ROADMAP ETAPA I step 5 — leave unchanged.
- [x] Confirm the "Adding a new feature" section (`CLAUDE.md:196–207`)
      already describes from-scratch creation with no scaffold-recovery
      prose — leave unchanged.
- [x] Confirm the `## Production checklist` (`CLAUDE.md:230–247`) and both
      "Key env vars" tables (`CLAUDE.md:249–278`) match the four
      infrastructure `composition/settings.py:validate_production` validators
      (`email` refuses `console`; `background_jobs` refuses `in_process`;
      `file_storage` refuses `local` when `APP_STORAGE_ENABLED=true`;
      `outbox` must be enabled) and the auth validator surface — leave
      unchanged.

## 2. Edit (the only two surgical changes)

- [x] `CLAUDE.md:50`: change "Six features ship out of the box." to
      "Seven features ship out of the box." Change no other word of the
      sentence.
- [x] `CLAUDE.md:164`: replace
      `` - `adapters/outbound/s3/` — stub; raises `NotImplementedError` ``
      with a code-true line describing the real `boto3`-backed adapter
      selected via `APP_STORAGE_BACKEND=s3` (consistent with `CLAUDE.md:60`,
      the canonical `project-layout` S3 paragraph, and
      `src/features/file_storage/__init__.py`). The words "stub",
      `NotImplementedError`, and "placeholder" MUST NOT appear for the S3
      adapter.

## 3. Post-edit verification

- [x] Re-grep `CLAUDE.md`: zero `s3 stub` / S3-`NotImplementedError` /
      "placeholder" hits for the S3 adapter; the only `NotImplementedError`
      hit remaining is the unrelated migration-`downgrade()` /
      destructive-migration convention prose.
- [x] Confirm no `src/cli/` section was added (ROADMAP step 12 deferral).
- [x] Confirm no file other than `CLAUDE.md` and the OpenSpec change
      artifacts was modified (`README.md`, `docs/`, code, tests, migrations
      untouched).
- [x] `openspec validate claude-md-reframe --strict` passes.

## 4. Archive (at archive time, not now)

- [ ] Reconcile `specs/project-layout/spec.md` against the **then-current**
      canonical `openspec/specs/project-layout/spec.md` "Documentation
      reflects the new layout" block — re-copy verbatim if step 7
      (`fix-s3-stub-drift`) or any other in-flight project-layout change
      landed first, so the restatement still byte-matches and no prior
      refinement is dropped.
- [ ] Archive WITHOUT `--skip-specs` (`openspec archive claude-md-reframe`)
      so the new CLAUDE.md scenario folds into the canonical
      `project-layout` spec.
