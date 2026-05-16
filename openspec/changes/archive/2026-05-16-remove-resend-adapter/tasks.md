# Tasks — remove-resend-adapter

## 1. Delete the Resend adapter package

- [ ] Delete `src/features/email/adapters/outbound/resend/adapter.py`
- [ ] Delete `src/features/email/adapters/outbound/resend/__init__.py`
- [ ] Delete the now-empty `src/features/email/adapters/outbound/resend/`
      directory (including any `__pycache__`)

## 2. Settings surface

- [ ] In `src/app_platform/config/settings.py`: narrow `email_backend` to
      `Literal["console"]`; remove `email_resend_api_key` and
      `email_resend_base_url`; remove the Resend lines from the Email comment
      block; reword the `console`/`resend` description so it states `console`
      is the only backend and production has no email transport until AWS SES
      (a later roadmap step). Keep `email_from` and `email_console_log_bodies`.
- [ ] In `src/features/email/composition/settings.py`: narrow `EmailBackend`
      to `Literal["console"]`; remove the `resend_api_key` and
      `resend_base_url` dataclass fields; remove the `resend_api_key` /
      `resend_base_url` keyword params from `from_app_settings`; remove the
      two `app.email_resend_*` assignments in the `if app is not None:`
      branch; narrow the `backend not in ("console", "resend")` guard and its
      error message to `("console",)` / lists only `'console'`; delete the
      `if self.backend == "resend":` block in `validate()`; remove the
      now-unreferenced `resolved_from_address()` method (only the deleted
      Resend arm called it — confirm with a grep before deleting); reword
      `validate_production` so it still appends an error when
      `backend == "console"` but the message no longer names `resend` (state
      that no production email backend exists yet — AWS SES arrives at a later
      roadmap step)

## 3. Composition

- [ ] In `src/features/email/composition/container.py`: remove the entire
      `elif settings.backend == "resend":` arm (api-key guard, deferred
      `from features.email.adapters.outbound.resend import ResendEmailAdapter`,
      the `httpx`-missing `RuntimeError`, adapter construction); remove the
      module-level `httpx`/`resend`-extra comment block. The trailing
      `else: raise RuntimeError(f"Unknown email backend: ...")` guard stays;
      `console` is the only remaining branch
- [ ] Audited & confirmed — **no edit** to `src/main.py`, `src/worker.py`,
      `src/cli/create_super_admin.py`, or
      `src/features/authentication/tests/e2e/conftest.py`: none pass any
      `resend_*` kwarg to `EmailSettings.from_app_settings` (verify with a
      grep during implementation; the only `resend_*` references are inside
      `EmailSettings.from_app_settings` itself and `AppSettings`)

## 4. Config files and tooling

- [ ] In `.env.example`: remove `APP_EMAIL_RESEND_API_KEY` and
      `APP_EMAIL_RESEND_BASE_URL` and the
      `# Resend — fill these when APP_EMAIL_BACKEND=resend` comment line;
      reword the `# Email.` / `# `resend` is the production-shaped backend`
      comment so it no longer names `resend` (state `console` is the only
      backend; production email arrives with AWS SES later)
- [ ] In `pyproject.toml`: remove the `resend = ["httpx>=0.28.1"]` extra and
      its three-line `# Resend email adapter. ...` comment block; remove the
      `#   uv sync --extra resend       # Resend email adapter` install-modes
      comment line; remove the `dev`-group `"httpx>=0.28.1",` and
      `"respx>=0.21",` entries (httpx audit: no `src/` code imports
      `httpx`/`respx` after this change). **Do NOT touch**
      `opentelemetry-instrumentation-httpx` (runtime OTel instrumentor,
      no-ops without httpx) or the `"httpx"` entries in the Import Linter
      `forbidden_modules` lists (architectural guardrails)
- [ ] Run `uv lock` so `uv.lock` drops `httpx`/`respx` (and any transitive
      deps now unused). Commit the regenerated lock

## 5. Tests

- [ ] Delete `src/features/email/tests/unit/test_resend_adapter.py`
- [ ] In `src/features/email/tests/contracts/test_email_port_contract.py`:
      remove `import httpx`, `import respx`, the
      `from features.email.adapters.outbound.resend import ResendEmailAdapter`
      import, the `_RESEND_BASE_URL` constant, the `_resend_factory` function,
      the `resend_mock` fixture, and the `resend` parametrisation id /
      `_resend_factory` entry; drop the now-unused `resend_mock` parameter
      from `test_valid_send_returns_ok`. Keep the `console` and `fake`
      factories and all their scenarios
- [ ] In `src/app_platform/tests/test_settings.py`: in `_VALID_PROD_ENV`,
      change `"APP_EMAIL_BACKEND": "resend"` to
      `"APP_EMAIL_BACKEND": "console"` and remove the
      `"APP_EMAIL_RESEND_API_KEY": "re_test_key"` entry; delete
      `test_resend_backend_requires_api_key`,
      `test_resend_backend_requires_from`, and
      `test_production_accepts_resend_backend`; ensure a test asserts
      `APP_ENVIRONMENT=production` + `APP_EMAIL_BACKEND=console` raises a
      `ValidationError` whose message reports the email-backend problem and
      names no removed backend; for every other test that loads
      `_VALID_PROD_ENV` and asserts a *different* refusal, isolate the
      now-always-present email-backend error so the assertion still targets
      its own env var (the email-backend refusal is unconditionally present
      in any production env after this change)
- [ ] In `src/app_platform/tests/unit/observability/test_configure_tracing.py`:
      in `test_production_ratio_one_emits_warning`, change
      `email_backend="resend"` + `email_resend_api_key="re_test_key"` to
      `email_backend="console"` and drop `email_resend_api_key` (this
      constructor builds `AppSettings` with explicit kwargs and asserts a
      tracing warning, not a boot — the production validator is not the path
      under test; confirm it still constructs)

## 6. Docs (Resend lines only — no wholesale rewrite)

- [ ] `docs/email.md`: remove the "Resend adapter" registry row, the
      `APP_EMAIL_RESEND_*` env-table rows, the `APP_EMAIL_BACKEND` `resend`
      note, the `resend`-credentials validator bullet, and the
      `### Resend (ResendEmailAdapter)` / `#### Acquiring an API key` /
      `#### Region (EU vs US)` sections and the
      "Resend contract path is exercised by `respx`" sentence; change
      "two adapters (console, Resend)" → "one adapter (console)"; state
      production email arrives with AWS SES at a later roadmap step
- [ ] `docs/operations.md`: remove the `uv sync --extra resend` install-modes
      table row, the
      `APP_EMAIL_BACKEND=resend without --extra resend → httpx ...` example
      bullet, and the four `APP_EMAIL_*` env-reference rows naming
      `resend`/`APP_EMAIL_RESEND_*` (lines ~816–819); replace with the
      minimal accurate post-removal reality (`APP_EMAIL_BACKEND` accepts only
      `console`; production has no email backend until AWS SES). Do NOT
      rewrite the broader "production refuses to start if…" narrative —
      ROADMAP step 11 owns that
- [ ] `docs/architecture.md`: email-feature table row
      "console + Resend adapters" → "console adapter (dev/test); production
      email arrives with AWS SES at a later roadmap step" (line ~34)
- [ ] `README.md`: docs-link "console/Resend adapters" → "console adapter";
      feature-table row "`EmailPort` plus `console` and `resend` adapters"
      → "`EmailPort` plus the `console` adapter (dev/test)"; tree comment
      "console/Resend adapters" → "console adapter"; key-env-var row
      "`APP_EMAIL_BACKEND` ... `resend` in production" → state `console` is
      the only backend / production email not yet available (AWS SES later)
- [ ] `CLAUDE.md`: feature-table row "console + Resend adapters" →
      "console adapter (dev/test); production email arrives with AWS SES at a
      later roadmap step"; Production-checklist bullet
      "`APP_EMAIL_BACKEND=console` (must be `resend` ...)" → state `console`
      is the only backend and production email is not yet available (AWS SES
      at a later roadmap step); remove the `APP_EMAIL_RESEND_API_KEY` and
      `APP_EMAIL_RESEND_BASE_URL` key-env-var rows; `APP_EMAIL_BACKEND` row
      note → drop `resend`
- [x] `CONTRIBUTING.md`: a re-audit found two real Resend-adapter references
      the removal invalidates — fixed both, minimally and in the surrounding
      style: the `test(email): add Resend retry contract` commit-subject
      example → `test(email): add console adapter contract`, and the
      pre-deploy checklist item `Email backend is \`resend\` with credentials
      set.` → `Email backend: production email requires the AWS SES adapter
      (added in a later roadmap step); \`console\` is dev/test only.`. The
      unrelated English-verb "resend" slugs in the commit/branch examples
      (`email-verification resend`, `feat/email-verification-resend`) are
      left untouched, re-confirmed not Resend-adapter-related

## 7. Verify

- [ ] `make lint-arch` — no new import-linter violation involving
      `src.features.email`
- [ ] `make quality` green (lint + arch + typecheck)
- [ ] `make test` green; specifically the email contract suite passes for
      `console` and `fake`
- [ ] `grep -rin 'resend\|RESEND\|httpx\|respx' src docs *.md
      .env.example pyproject.toml` returns no Resend hit and no `httpx`/
      `respx` hit other than the kept `opentelemetry-instrumentation-httpx`
      runtime dep, the kept Import Linter `forbidden_modules` `"httpx"`
      guardrails, the kept `APP_OTEL_INSTRUMENT_HTTPX` toggle / its
      string-patch test, and `CONTRIBUTING.md`'s English-verb examples
- [ ] `openspec validate remove-resend-adapter --strict` passes
