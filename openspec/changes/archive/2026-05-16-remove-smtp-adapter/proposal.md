## Why

ROADMAP ETAPA I step 3 ("dejar el repo honesto"): remove the SMTP email
adapter and every config/test/doc surface that promises it. The starter is
moving to an AWS-first posture; the SMTP backend is a third email path that no
longer pays its way:

1. **It carries a full adapter, three call sites, and a dependency for a path
   the roadmap is removing.** `SmtpEmailAdapter` (two modules), nine
   `email_smtp_*` fields on `AppSettings`, the matching `smtp_*` projection on
   `EmailSettings` (fields, factory kwargs, the `from_app_settings(app)`
   assignments, and a `validate()` branch), the `smtp` arm of
   `build_email_container`, and three composition call sites
   (`src/main.py`, `src/worker.py`, `src/cli/create_super_admin.py`) that each
   forward eight `smtp_*` kwargs. A dedicated `aiosmtpd>=1.4.6` test dependency
   exists in the `dev` group **solely** to run the SMTP adapter's unit test.
2. **It widens the public config contract with knobs no one should set.**
   `.env.example` ships seven `APP_EMAIL_SMTP_*` keys plus a mailpit how-to
   comment block; `docs/email.md`, `docs/operations.md`, and
   `docs/development.md` document the SMTP env vars and a "Local Email With
   Mailpit" workflow. An operator reading these cannot tell the SMTP path is
   being retired.
3. **It runs a `mailpit` container nobody needs by default.**
   `docker-compose.yml` always starts a `mailpit` service (ports `1025`/`8025`)
   whose only purpose is to catch SMTP that the default `console` backend never
   sends. It is dev noise.

This step deletes the SMTP backend only. `console` (the dev/test fake) and
`resend` (the production HTTP backend) are unchanged. The production validator
still refuses `console` in production — it now points operators at `resend`,
which is the only remaining production-shaped backend until ROADMAP step 4
removes Resend in its own change.

## What Changes

- Delete the SMTP adapter package
  `src/features/email/adapters/outbound/smtp/` (`__init__.py`, `adapter.py`).
- Remove the nine `email_smtp_*` fields and their comment block from
  `AppSettings` and narrow `email_backend` from
  `Literal["console", "smtp", "resend"]` to `Literal["console", "resend"]`
  (`src/app_platform/config/settings.py`).
- Remove every `smtp_*` member from the `EmailSettings` projection: the eight
  dataclass fields, the eight `from_app_settings` keyword params, the eight
  `app.email_smtp_*` assignments in the `app is not None` branch, the
  `EmailBackend` `Literal` narrowing, the `"smtp"` arm of the
  `backend not in (...)` guard, and the `if self.backend == "smtp":` branch in
  `validate()` (`src/features/email/composition/settings.py`).
- Remove the `elif settings.backend == "smtp":` arm (host guard + adapter
  construction) and the `from ...smtp import SmtpEmailAdapter` import from
  `build_email_container` (`src/features/email/composition/container.py`).
- Remove the eight `smtp_*=app_settings.email_smtp_*` kwargs from all three
  `EmailSettings.from_app_settings(...)` call sites
  (`src/main.py`, `src/worker.py`, `src/cli/create_super_admin.py`).
- Remove the seven `APP_EMAIL_SMTP_*` keys and the mailpit how-to comment
  block from `.env.example`; keep `APP_EMAIL_BACKEND`, `APP_EMAIL_FROM`, and
  the `APP_EMAIL_RESEND_*` keys.
- Remove the `mailpit` service from `docker-compose.yml`. (Audited: no other
  service has a `depends_on` or reference to it, so no further compose edits.)
- Remove the `aiosmtpd>=1.4.6` entry from the `dev` dependency group in
  `pyproject.toml`. SMTP used stdlib `smtplib`, so there is **no runtime
  dependency or extra to remove** — `aiosmtpd` was a test-only server used
  exclusively by the deleted SMTP adapter test.
- Delete `src/features/email/tests/unit/test_smtp_adapter.py` (the only test of
  the deleted adapter; its `aiosmtpd` fixture is the sole `aiosmtpd` consumer
  outside an incidental string literal).
- Delete the three SMTP unit tests in `src/app_platform/tests/test_settings.py`
  (`test_smtp_backend_requires_host`, `test_smtp_backend_requires_from`, and
  the SMTP env entries in the shared `_VALID_PROD_ENV` dict) and switch the
  shared production-env baseline from `APP_EMAIL_BACKEND=smtp` /
  `APP_EMAIL_SMTP_HOST` to `APP_EMAIL_BACKEND=resend` /
  `APP_EMAIL_RESEND_API_KEY` so the remaining production tests still construct
  a valid `AppSettings`.
- Update `src/features/authentication/tests/e2e/conftest.py`: drop the seven
  `smtp_*` kwargs from its `EmailSettings.from_app_settings(...)` call (it
  builds a `console` container — the kwargs are now invalid).
- Update `src/app_platform/tests/unit/observability/test_configure_tracing.py`:
  the AppSettings fixture sets `email_backend="smtp"` + `email_smtp_*`; switch
  it to `email_backend="resend"` + `email_resend_api_key=...` so the fixture
  still constructs.
- Remove SMTP/mailpit lines **only** from `docs/email.md`, `docs/operations.md`,
  `docs/development.md`, `docs/architecture.md`, `README.md`, `CONTRIBUTING.md`,
  and `CLAUDE.md` (the email-feature row "console + SMTP + Resend adapters" →
  "console + Resend adapters"; the production-checklist line; the SMTP
  env-table rows; the "Local Email With Mailpit" section). The broader doc
  rewrites are ROADMAP steps 9/10/11 and are explicitly out of scope here.

**Production-validator coherence (required by the constraint):** the email
production validator currently refuses `console` and accepts `smtp` or
`resend`. After this step `smtp` no longer exists, so the validator SHALL
refuse `console` and accept **only** `resend` (with its required fields). This
is the minimum change removing SMTP forces — it does not pre-empt ROADMAP
step 4 (Resend removal) or step 11 (full `operations.md` reconciliation).

**Capabilities — Modified**
- `email`: the backend-selection and production-validator requirements no
  longer enumerate `smtp`.
- `project-layout`: the email-adapter log-redaction requirement no longer
  enumerates the SMTP adapter (its two SMTP-specific scenarios are removed; the
  console/Resend redaction guarantees are unchanged).
- `quality-automation`: the docker-compose dev-tooling requirement no longer
  mandates a `mailpit` SMTP catcher; the surviving `app`-service
  restart/healthcheck guarantee and the console-default guarantee are restated
  without the SMTP wording.

**Capabilities — New**
- None.

## Impact

- **Deleted package**: `src/features/email/adapters/outbound/smtp/`
  (`__init__.py`, `adapter.py`).
- **Code**:
  - `src/app_platform/config/settings.py` (narrow `email_backend` Literal;
    remove nine `email_smtp_*` fields + comment block)
  - `src/features/email/composition/settings.py` (remove all `smtp_*`
    fields/kwargs/assignments, `EmailBackend` Literal, guard arm, `validate()`
    SMTP branch)
  - `src/features/email/composition/container.py` (remove the `smtp` arm +
    `SmtpEmailAdapter` import)
  - `src/main.py`, `src/worker.py`, `src/cli/create_super_admin.py` (remove
    `smtp_*` kwargs from the three `from_app_settings` calls)
  - `.env.example` (remove seven `APP_EMAIL_SMTP_*` keys + mailpit comment
    block)
  - `docker-compose.yml` (remove the `mailpit` service)
  - `pyproject.toml` (remove `aiosmtpd>=1.4.6` from the `dev` group)
- **Tests**:
  - Delete `src/features/email/tests/unit/test_smtp_adapter.py`.
  - Delete `test_smtp_backend_requires_host` and `test_smtp_backend_requires_from`
    in `src/app_platform/tests/test_settings.py`; repoint the shared
    `_VALID_PROD_ENV` baseline from `smtp` to `resend`.
  - Edit `src/features/authentication/tests/e2e/conftest.py` (drop `smtp_*`
    kwargs).
  - Edit `src/app_platform/tests/unit/observability/test_configure_tracing.py`
    (repoint fixture from `smtp` to `resend`).
  - The shared contract suite
    `src/features/email/tests/contracts/test_email_port_contract.py` is
    **NOT parametrized over SMTP** — its factories are
    `[console, fake, resend]`. No contract-test edit is required; the suite
    keeps passing for the remaining backends untouched.
  - `src/features/email/tests/unit/test_send_email_job_log_redaction.py` only
    uses the string `"smtp 550"` as an arbitrary fake `DeliveryError` reason;
    it imports nothing SMTP and asserts nothing SMTP-specific. No edit
    required (an optional cosmetic reason-string rename is allowed but not
    in scope).
- **Migrations**: none. No table, column, index, or persisted state is
  touched. SMTP was a runtime dispatch path with zero database footprint.
- **Docs** (SMTP/mailpit lines only — no wholesale rewrite):
  `docs/email.md`, `docs/operations.md`, `docs/development.md`,
  `docs/architecture.md`, `README.md`, `CONTRIBUTING.md`, `CLAUDE.md`.
- **Production behavior**: the only behavioral change is the production
  validator's accepted set: it refused `console` and accepted `{smtp, resend}`;
  it now refuses `console` and accepts `{resend}`. Any deployment running
  `APP_EMAIL_BACKEND=smtp` will now fail fast at startup with a clear message —
  intended, since the SMTP backend is gone. `APP_EMAIL_SMTP_*` env vars become
  unknown keys (pydantic-settings ignores extra env vars by default; confirm
  during implementation that `model_config` does not set `extra="forbid"`).
- **Quality gate**: `make quality` and `make test` MUST stay green after the
  removal. The email contract suite MUST still pass for `console`, `fake`, and
  `resend`. Removing the adapter, its test, its dependency, and its config
  surface together keeps the suite and the import-linter contracts consistent.

## Out of scope (do NOT touch)

- The Resend adapter (`src/features/email/adapters/outbound/resend/`), the
  `APP_EMAIL_RESEND_*` env vars, the `resend` extra, and every `resend`
  requirement/scenario in `openspec/specs/email/spec.md` — that removal is
  ROADMAP step 4, a separate change.
- The `console` adapter (`src/features/email/adapters/outbound/console/`) — it
  is the dev/test default fake and stays.
- Any broader rewrite of `README.md`, `CLAUDE.md`, or `docs/operations.md`
  beyond deleting SMTP/mailpit lines — ROADMAP steps 9/10/11 own those.
- The email spec's `Adapters do not import from inbound or other features`
  requirement — it references only the Resend/`httpx` import rule, not SMTP,
  so it does not change here.

This change is strictly ROADMAP ETAPA I step 3. It does not advance steps
4–8 (Resend/arq/SpiceDB/S3 removal, api.md) or any ETAPA II+ work.
