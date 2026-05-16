# Tasks — operations-md-reconcile (ROADMAP ETAPA I step 11)

## 1. Audit (verify the already-correct state — do NOT churn)

- [x] Confirm `APP_WRITE_API_KEY` is a phantom: `rg 'WRITE_API_KEY|write_api_key' src/`
      returns **zero** hits; no `composition/settings.py` projection and no
      `src/app_platform/config/sub_settings.py` projection defines it; no
      inbound HTTP route is gated by a shared API key (write routes use
      `require_authorization`).
- [x] Confirm the Environment Variable Reference (`docs/operations.md:708–842`)
      — the consolidated "settings validator refuses to start when any of
      them are violated" master list — matches the four infrastructure
      `composition/settings.py:validate_production` validators and
      `AppSettings._validate_production_settings`, and correctly does **not**
      list `APP_WRITE_API_KEY` in any per-feature table. Leave unchanged.
- [x] Confirm the Email row (`:806`) — `console`-only, production refuses
      it, SES later — matches the email `validate_production`. Leave
      unchanged.
- [x] Confirm the Background Jobs section (`:583–604`) and env row (`:813`)
      — `in_process`-only, production refuses it, AWS SQS + Lambda later,
      arq removed in ROADMAP ETAPA I step 5 — match the background_jobs
      `validate_production`. Leave unchanged.
- [x] Confirm the File Storage rows (`:838–842`) and S3 prose (`:24`,
      `:35`, `:881`) — real `boto3` `s3` backend, `s3` required in
      production when `APP_STORAGE_ENABLED=true`, **no** "stub" /
      `NotImplementedError` / "placeholder" wording — match the
      file_storage `validate_production` and steps 7/9/10. Leave unchanged.
- [x] Confirm the Outbox row (`:823`) — must be `true` in production —
      matches the outbox `validate_production`. Leave unchanged.
- [x] Confirm the Redis-URL (`:387–390`), trusted-proxy (`:404–411`),
      trusted-hosts (`:170`/`:726`), docs / CORS / cookie / RBAC /
      return-internal-tokens production rules match
      `AppSettings._validate_production_settings`. Leave unchanged.
- [x] Grep `docs/operations.md` for `SMTP`/`smtp`, `Resend`/`resend`,
      `SpiceDB`/`spicedb`, `mailpit`, `_template`, `feature-template`,
      `recover the scaffold`, `recoverable` — confirm **zero** hits
      (already purged by ETAPA I steps 3–7). Do not fabricate work.
- [x] Confirm the two `arq` references (`:22`, `:116`) and the `:594`
      "removed in ROADMAP ETAPA I step 5" note are accurate — leave
      unchanged.
- [x] Confirm the destructive-migration `downgrade()` / `NotImplementedError`
      guard (`:219–273`) is unrelated to S3 / ETAPA I cleanup — leave
      exactly as-is (including the "template-only schema" DB-lifetime
      phrase).
- [x] Confirm the incidental `python -m cli.create_super_admin` /
      `src/cli/create_super_admin.py` bootstrap-runbook mentions
      (`:300–305`, `:331`) are accurate operational prose, NOT a `src/cli/`
      command-reference catalogue — leave unchanged (step 12 owns the
      catalogue).

## 2. Edit (the only surgical change)

- [x] `docs/operations.md:173`: delete the Deployment Checklist bullet
      `- Set `APP_WRITE_API_KEY` if write routes should require a shared
      key.` entirely. Do **not** add a replacement bullet — there is no
      real "shared key for write routes" knob. Change no other bullet in
      the Deployment Checklist (`:164–178`).

## 3. Post-edit verification

- [ ] Re-grep `docs/operations.md`: **zero** `WRITE_API_KEY` / `X-API-Key`
      hits; **zero** `SMTP`/`Resend`/`SpiceDB`/`mailpit`/`_template` hits.
      The only remaining `arq` hits are the "removed in ROADMAP ETAPA I
      step 5" references; the only `scaffold` hits are the runtime-agnostic
      worker-scaffold wording; the only `NotImplementedError` hits are the
      destructive-migration `downgrade()` guard; the only `stub` hit is the
      unrelated "no row stub" GDPR retention note (`:924`); the only
      `recovery`/`recover` hits are the DB restore-from-backup runbook.
- [ ] Confirm no `src/cli/` command-reference section was added (ROADMAP
      step 12 deferral); the bootstrap-runbook `cli` mentions are
      unchanged.
- [ ] Confirm no file other than `docs/operations.md` and the OpenSpec
      change artifacts was modified (`README.md`, `CLAUDE.md`, other
      `docs/`, code, tests, migrations untouched).
- [ ] `openspec validate operations-md-reconcile --strict` passes.

## 4. Archive (at archive time, not now)

- [ ] Reconcile `specs/project-layout/spec.md` against the **then-current**
      canonical `openspec/specs/project-layout/spec.md` "Documentation
      reflects the new layout" block — re-copy verbatim if step 7
      (`fix-s3-stub-drift`) or any other in-flight project-layout change
      landed first, so the restatement still byte-matches and no prior
      refinement (src.-prefix, scaffold-recovery, api.md, S3-stub, README
      AWS-first, CLAUDE seven-feature) is dropped.
- [ ] Archive WITHOUT `--skip-specs`
      (`openspec archive operations-md-reconcile`) so the new
      operations.md scenario folds into the canonical `project-layout`
      spec.
