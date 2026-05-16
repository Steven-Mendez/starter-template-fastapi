# Tasks — remove-smtp-adapter

## 1. Delete the SMTP adapter package

- [x] Delete `src/features/email/adapters/outbound/smtp/adapter.py`
- [x] Delete `src/features/email/adapters/outbound/smtp/__init__.py`
- [x] Delete the now-empty `src/features/email/adapters/outbound/smtp/` directory

## 2. Settings surface

- [x] In `src/app_platform/config/settings.py`: narrow `email_backend` to
      `Literal["console", "resend"]`; remove `email_smtp_host`,
      `email_smtp_port`, `email_smtp_username`, `email_smtp_password`,
      `email_smtp_use_starttls`, `email_smtp_use_ssl`,
      `email_smtp_timeout_seconds` and the SMTP lines in the Email comment
      block (keep the `console`/`resend` description, adjust the
      "refuses `console`" wording so it no longer names `smtp`)
- [x] In `src/features/email/composition/settings.py`: narrow
      `EmailBackend` to `Literal["console", "resend"]`; remove the eight
      `smtp_*` dataclass fields; remove the eight `smtp_*` keyword params
      from `from_app_settings`; remove the eight `app.email_smtp_*`
      assignments in the `if app is not None:` branch; drop `"smtp"` from
      the `backend not in (...)` guard and its error message; delete the
      `if self.backend == "smtp":` block in `validate()`; confirm
      `validate_production` still refuses `console` (no `smtp` text)

## 3. Composition

- [x] In `src/features/email/composition/container.py`: remove the
      `from features.email.adapters.outbound.smtp import SmtpEmailAdapter`
      import and the entire `elif settings.backend == "smtp":` arm (host
      guard + adapter construction). The trailing `else: raise RuntimeError`
      guard stays
- [x] Remove the eight `smtp_*=app_settings.email_smtp_*` kwargs from the
      `EmailSettings.from_app_settings(...)` call in `src/main.py`
- [x] Remove the eight `smtp_*=app_settings.email_smtp_*` kwargs from the
      `EmailSettings.from_app_settings(...)` call in `src/worker.py`
- [x] Remove the eight `smtp_*=settings.email_smtp_*` kwargs from the
      `EmailSettings.from_app_settings(...)` call in
      `src/cli/create_super_admin.py`

## 4. Config files and tooling

- [x] In `.env.example`: remove the seven `APP_EMAIL_SMTP_*` keys and the
      mailpit how-to comment block; adjust the `# smtp and resend ...`
      comment so it no longer names `smtp`
- [x] In `docker-compose.yml`: remove the `mailpit` service block (verify
      nothing `depends_on` it — audited clean)
- [x] In `pyproject.toml`: remove `"aiosmtpd>=1.4.6",` from the `dev`
      dependency group; run `uv lock` so `uv.lock` drops `aiosmtpd`

## 5. Tests

- [x] Delete `src/features/email/tests/unit/test_smtp_adapter.py`
- [x] In `src/app_platform/tests/test_settings.py`: change the shared
      `_VALID_PROD_ENV` from `"APP_EMAIL_BACKEND": "smtp"` +
      `"APP_EMAIL_SMTP_HOST": "smtp.example.com"` to
      `"APP_EMAIL_BACKEND": "resend"` +
      `"APP_EMAIL_RESEND_API_KEY": "re_test_key"`; delete
      `test_smtp_backend_requires_host` and `test_smtp_backend_requires_from`;
      fix `test_production_accepts_resend_backend` if its comment/asserts
      reference the now-removed SMTP baseline fields
- [x] In `src/features/authentication/tests/e2e/conftest.py`: remove the
      `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password`,
      `smtp_use_starttls`, `smtp_use_ssl`, `smtp_timeout_seconds` kwargs
      from the `EmailSettings.from_app_settings(...)` call (it builds a
      `console` container)
- [x] In `src/app_platform/tests/unit/observability/test_configure_tracing.py`:
      change `email_backend="smtp"` + `email_smtp_*` to
      `email_backend="resend"` + `email_resend_api_key="re_test_key"` in the
      AppSettings fixture
- [ ] (Optional, cosmetic, not required — intentionally skipped per scope)
      rename the `"smtp 550"` reason string in
      `src/features/email/tests/unit/test_send_email_job_log_redaction.py`

## 6. Docs (SMTP/mailpit lines only — no wholesale rewrite)

- [x] `docs/email.md`: remove the "SMTP adapter" registry row, the
      `APP_EMAIL_SMTP_*` env-table rows, the SMTP validator bullet, the
      `### SMTP (SmtpEmailAdapter)` section, and the
      "the SMTP path uses a fake SMTP server provided by `aiosmtpd`"
      sentence; adjust "three adapters (console, SMTP, Resend)" →
      "two adapters (console, Resend)"
- [x] `docs/operations.md`: remove the seven `APP_EMAIL_SMTP_*` rows from
      the env-var reference table; in the dependency-matrix table change the
      `SMTP server` row's trigger so it no longer says
      `APP_EMAIL_BACKEND=smtp` is required in production (it is now Resend);
      adjust `APP_EMAIL_BACKEND` row note ("Must be `smtp` or `resend`" →
      "Must be `resend`") and the `APP_EMAIL_FROM` row note
- [x] `docs/development.md`: remove the entire
      `## Local Email With Mailpit` section
- [x] `docs/architecture.md`: email-feature row
      "console + SMTP adapters" → "console + Resend adapters" (line ~34);
      remove the `SMTP server` dependency-matrix row (line ~190)
- [x] `README.md`: remove `aiosmtpd` from the Testing tool row; change
      "console/SMTP adapters" → "console/Resend adapters" in the docs link
      and feature table and the tree comment; change
      "`APP_EMAIL_BACKEND` ... `smtp` in production" →
      "`resend` in production"; change the production-checklist line
      "Email backend is `smtp` or `resend`" → "Email backend is `resend`"
- [x] `CONTRIBUTING.md`: change `docs/development.md` index note
      "Local workflow, Mailpit, debugging tips" → drop "Mailpit"; the
      `test(email): add SMTP STARTTLS contract` example may be reworded to
      a non-SMTP example
- [x] `CLAUDE.md`: email-feature row "console + SMTP + Resend adapters" →
      "console + Resend adapters"; in `### Email feature`, change
      "console + SMTP + Resend adapters" wording; in the Production
      checklist, change "`APP_EMAIL_BACKEND=console` (must be `smtp` or
      `resend` ...)" → "(must be `resend` ...)"; key-env-var table
      `APP_EMAIL_BACKEND` note → drop `smtp`

## 7. Verify

- [x] `make lint-arch` — no new import-linter violation involving
      `src.features.email`
- [x] `make quality` green (lint + arch + typecheck)
- [x] `make test` green; specifically the email contract suite passes for
      `console`, `fake`, `resend`
- [x] `grep -ri 'smtp\|mailpit\|aiosmtpd' src docs *.md docker-compose.yml
      .env.example pyproject.toml` returns no SMTP/mailpit hit (the
      `oauth2-redirect`-style false positives do not apply here)
- [x] `openspec validate remove-smtp-adapter --strict` passes
