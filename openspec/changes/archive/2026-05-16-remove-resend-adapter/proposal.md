## Why

ROADMAP ETAPA I step 4 ("dejar el repo honesto"): remove the Resend email
adapter and every config/test/doc surface that promises it. Step 3 already
deleted SMTP; Resend was deliberately kept then as "the only remaining
production-shaped backend until ROADMAP step 4 removes it in its own change".
This is that change. The starter is AWS-first; the explicit ROADMAP decisions
are: remove non-AWS production-shaped adapters (SMTP, Resend, arq, SpiceDB),
keep dev-only adapters (`console`), and add the real `aws_ses` adapter at
ROADMAP step 25. The Resend backend no longer pays its way:

1. **It carries a full HTTP adapter, a dependency extra, and config surface
   for a path the roadmap is removing.** `ResendEmailAdapter` (two modules)
   imports `httpx`; two `email_resend_*` fields plus a comment block on
   `AppSettings`; the matching `resend_api_key` / `resend_base_url` projection
   on `EmailSettings` (fields, the `from_app_settings(app)` assignments, the
   `from_app_settings` kwargs, the `backend not in (...)` guard, the
   `if self.backend == "resend":` `validate()` branch, and the
   `resolved_from_address()` default sender that only the Resend arm reads);
   the `resend` arm of `build_email_container` with its deferred-import
   `httpx`-missing guard; the `resend = ["httpx>=0.28.1"]` optional-dependency
   extra and its comment block.
2. **It widens the public config contract with knobs no one should set.**
   `.env.example` ships two `APP_EMAIL_RESEND_*` keys plus a "fill these when
   `APP_EMAIL_BACKEND=resend`" comment; `docs/email.md`, `docs/operations.md`,
   `docs/architecture.md`, `README.md`, and `CLAUDE.md` document the Resend env
   vars, the `resend` install extra, region selection, and an "Acquiring an API
   key" workflow. An operator reading these cannot tell the Resend path is
   being retired ahead of AWS SES.
3. **`email_backend` collapses to a single value.** With Resend gone,
   `Literal["console", "resend"]` becomes `Literal["console"]` — `console` is
   the only backend. Every multi-backend branch (`build_email_container`'s
   `elif`, the `from_app_settings` guard listing two names, the contract
   suite's three-way parametrisation) is now a degenerate one-arm dispatch
   carrying dead alternatives.

This step deletes the Resend backend only. `console` (the dev/test fake) is
unchanged and remains the sole adapter. The real production email backend
(`aws_ses`) is ROADMAP step 25 and is explicitly out of scope here.

### Key decision — the production email validator stays a refusal

Removing Resend leaves `console` as the only `email_backend` value. The email
production validator currently refuses `console` when
`APP_ENVIRONMENT=production` (`src/features/email/composition/settings.py`,
`validate_production`). After this step there is **no production-capable email
backend at all** until ROADMAP step 25 adds `aws_ses`.

**Decision: keep the refusal honest — the validator SHALL continue to refuse
`console` in production.** Production-with-email is intentionally not bootable
until SES arrives. This is the correct, honest state of an AWS-first starter
mid-cleanup, for three reasons:

- **Safety invariant preserved.** The whole point of the refusal is "production
  must never silently send mail through the dev `console` sink" (which only
  logs `body_len`/`body_sha256` and discards the message — password-reset and
  email-verify mail would be black-holed). That risk does not disappear because
  `console` became the only value; it gets *worse* (now there is no safe
  alternative to fall back to). Relaxing the refusal so production boots on
  `console` would silently weaken production safety: a real deploy would come
  up "green" while every transactional email is dropped. An explicit boot
  failure with a clear message is strictly safer than a silent black hole.
- **Honest over convenient.** The ROADMAP's stated norte is "una sola opción
  opinada > tres opciones a medias" and "dejar el repo honesto". The honest
  statement after step 4 is: *this starter has no production email transport
  yet; it arrives at step 25*. A validator that refuses to boot says exactly
  that. A validator that accepts `console` in production would lie.
- **Minimal blast radius, no roadmap pre-emption.** Keeping the refusal means
  the *only* code change the refusal forces is wording: the message currently
  says "configure 'resend' and set the matching credentials"; `resend` no
  longer exists, so the message must stop naming it. The simplest honest
  replacement states that no production email backend exists yet and points at
  the roadmap (AWS SES). This does **not** pre-empt ROADMAP step 11 (the
  `docs/operations.md` "production refuses to start if…" narrative rewrite) or
  ROADMAP step 25 (the SES adapter and its accept-path). It is the minimum the
  Resend removal forces for code/test coherence.

Considered and rejected: *relax the refusal so production may boot on
`console`.* Rejected because it converts a loud, intentional "not ready yet"
into a silent mail black hole in production — the exact failure the validator
exists to prevent. The temporary inability to boot a production deployment
*with email* is not a regression introduced here; it is the truthful
consequence of removing the last non-AWS production backend before the AWS one
lands, and it is recoverable the moment step 25 ships `aws_ses`.

**Test consequence (called out because it is the non-obvious ripple):** the
shared `_VALID_PROD_ENV` baseline in `src/app_platform/tests/test_settings.py`
was repointed to `APP_EMAIL_BACKEND=resend` in step 3 so that the broad
production-validator tests could construct a *bootable* `AppSettings`. With no
bootable production email backend, that baseline can no longer represent a
fully-valid production env via the email axis. The baseline is repointed to
`APP_EMAIL_BACKEND=console`, and every test that consumes `_VALID_PROD_ENV` to
assert *some other* refusal must isolate the email-backend error from the
assertion (the email-backend refusal is now always present in a production
env). The dedicated email tests change from "console refused / resend accepted"
to "console refused, message names no removed backend, and no email backend is
accepted in production". The `resend`-specific tests
(`test_resend_backend_requires_api_key`, `test_resend_backend_requires_from`,
`test_production_accepts_resend_backend`) are deleted.

## What Changes

- Delete the Resend adapter package
  `src/features/email/adapters/outbound/resend/` (`__init__.py`, `adapter.py`).
- Narrow `email_backend` from `Literal["console", "resend"]` to
  `Literal["console"]`; remove the two `email_resend_api_key` /
  `email_resend_base_url` fields and the Resend comment block from
  `AppSettings` (`src/app_platform/config/settings.py`). Update the
  `console`/`resend` description comment to state `console` is the only
  backend and production has no email transport until AWS SES.
- In `src/features/email/composition/settings.py`: narrow `EmailBackend` to
  `Literal["console"]`; remove the `resend_api_key` and `resend_base_url`
  dataclass fields; remove the `resend_api_key`/`resend_base_url`
  `from_app_settings` keyword params and their two `app.email_resend_*`
  assignments in the `app is not None` branch; narrow the `backend not in
  (...)` guard to `("console",)`; remove the `if self.backend == "resend":`
  branch from `validate()`; remove the now-unreferenced
  `resolved_from_address()` method (only the deleted Resend arm called it);
  reword `validate_production` so it still refuses `console` but its message
  no longer names `resend` — it states no production email backend exists yet
  (AWS SES arrives at a later roadmap step).
- In `src/features/email/composition/container.py`: remove the
  `elif settings.backend == "resend":` arm (api-key guard, deferred
  `from ...resend import ResendEmailAdapter`, `httpx`-missing `RuntimeError`,
  adapter construction), remove the module-level `httpx`/`resend`-extra
  comment block; `console` becomes the only branch. Keep the final
  `else: raise RuntimeError(f"Unknown email backend: ...")` defensive arm.
- Remove the two `APP_EMAIL_RESEND_*` keys and the "fill these when
  `APP_EMAIL_BACKEND=resend`" comment from `.env.example`; reword the
  `# Email.` comment so it no longer calls `resend` "the production-shaped
  backend".
- Remove the `resend = ["httpx>=0.28.1"]` optional-dependency extra and its
  three-line comment block from `pyproject.toml`, and the
  `uv sync --extra resend` line from the install-modes comment block. **httpx
  audit (see Impact):** `httpx`/`respx` in the `dev` dependency group are
  removed (they exist only for the Resend adapter test and the Resend contract
  parametrisation; no other `src/` code imports either). `re-uv lock` is
  required after the `pyproject.toml` edits.
- Delete `src/features/email/tests/unit/test_resend_adapter.py` (the only test
  of the deleted adapter).
- De-parametrise `src/features/email/tests/contracts/test_email_port_contract.py`:
  drop the `_resend_factory`, the `resend` parametrisation id, the
  `resend_mock` fixture, the `_RESEND_BASE_URL` constant, and the
  `import httpx` / `import respx` / `from ...resend import ResendEmailAdapter`
  lines; keep `console` and `fake`. Drop the now-unused `resend_mock`
  parameter from `test_valid_send_returns_ok`.
- In `src/app_platform/tests/test_settings.py`: repoint the shared
  `_VALID_PROD_ENV` baseline from `APP_EMAIL_BACKEND=resend` /
  `APP_EMAIL_RESEND_API_KEY` to `APP_EMAIL_BACKEND=console` (drop the
  `APP_EMAIL_RESEND_API_KEY` entry); delete `test_resend_backend_requires_api_key`,
  `test_resend_backend_requires_from`, and `test_production_accepts_resend_backend`;
  add/keep a test asserting production refuses `console` with a message that
  names no removed backend; isolate the always-present email-backend error in
  every other `_VALID_PROD_ENV`-based production test so each still asserts its
  own target refusal.
- In `src/app_platform/tests/unit/observability/test_configure_tracing.py`:
  the `test_production_ratio_one_emits_warning` AppSettings fixture sets
  `email_backend="resend"` + `email_resend_api_key=...`; switch it to
  `email_backend="console"` and drop `email_resend_api_key`. (The production
  validator is *not* invoked in this constructor path — it builds `AppSettings`
  with explicit kwargs and asserts a tracing warning, not a boot — so
  `console` is accepted here; confirm during implementation.)
- Remove Resend lines **only** from `docs/email.md`, `docs/operations.md`,
  `docs/architecture.md`, `README.md`, and `CLAUDE.md`:
  - `docs/email.md`: drop the Resend adapter table row, the
    `APP_EMAIL_RESEND_*` env-var rows, the "validator refuses to start when"
    `resend`-credentials bullet, and the entire "Resend (`ResendEmailAdapter`)"
    / "Acquiring an API key" / "Region (EU vs US)" sections; restate the
    feature summary as "ships with a port, one adapter (`console`), and a
    template registry"; state production email arrives with AWS SES at a later
    roadmap step.
  - `docs/operations.md`: drop the `uv sync --extra resend` install-modes row,
    the `APP_EMAIL_BACKEND=resend` missing-extra example bullet, and the four
    `APP_EMAIL_*` env-reference rows that name `resend`/`APP_EMAIL_RESEND_*`;
    replace with the minimal accurate post-removal reality (`APP_EMAIL_BACKEND`
    accepts only `console`; production has no email backend until AWS SES).
    Do **not** rewrite the broader "production refuses to start if…" narrative
    — ROADMAP step 11 owns that.
  - `docs/architecture.md`, `README.md`, `CLAUDE.md`: the email-feature row
    "console + Resend adapters" / "console/Resend adapters" →
    "console adapter (dev/test); production email arrives with AWS SES at a
    later roadmap step" (minimal honest wording); drop the
    `APP_EMAIL_BACKEND ... resend in production` env-table rows; in `CLAUDE.md`
    change the production-checklist bullet
    `APP_EMAIL_BACKEND=console (must be resend ...)` to state `console` is the
    only backend and production email is not yet available (AWS SES at a later
    roadmap step). `CONTRIBUTING.md`: a re-audit found it has the unrelated
    English verb "resend" in example commit/branch slugs
    (`email-verification resend`) **and** two real Resend-adapter
    references the removal invalidates — a `test(email): add Resend retry
    contract` commit-subject example (the retry contract no longer exists)
    and a pre-deploy checklist item `Email backend is \`resend\` with
    credentials set.` (now actively misinstructs operators, since
    `APP_EMAIL_BACKEND=resend` hard-fails at startup post-change). Those two
    are corrected; the verb slugs are left untouched.

**Production-validator coherence (required by the constraint):** the email
production validator continues to refuse `console` in production (see "Key
decision" above). The only forced change is its message no longer naming the
removed `resend` backend; it now states no production email transport exists
yet. This does not pre-empt ROADMAP step 11 (operations.md narrative) or
ROADMAP step 25 (AWS SES adapter and its accept-path).

**Capabilities — Modified**
- `email`: the `Resend adapter is a real HTTP implementation` and
  `Resend base URL is configurable` requirements are removed entirely
  (REMOVED). `Email backend selection`, `Production settings validator`, and
  `Adapters do not import from inbound or other features` no longer enumerate
  `resend`/`httpx` and reflect `console` as the only backend with no
  production transport.
- `project-layout`: the email-adapter log-redaction requirement no longer
  enumerates the Resend adapter (its recipient-masking scenario is removed;
  the console redaction guarantee is unchanged).
- `quality-automation`: the dependency-split requirement no longer lists a
  `resend` extra or an `httpx`-missing Resend startup error; the surviving
  `api`/`worker`/`s3` split and the console-default guarantee are restated
  without Resend wording.
- `authentication`: `Every documented production refusal has a unit test`
  is restated so the email-backend refusal it implies is "no production email
  backend exists" rather than "console refused / resend accepted".

**Capabilities — New**
- None.

## Impact

- **Deleted package**: `src/features/email/adapters/outbound/resend/`
  (`__init__.py`, `adapter.py`).
- **Code**:
  - `src/app_platform/config/settings.py` (narrow `email_backend` to
    `Literal["console"]`; remove two `email_resend_*` fields + comment block;
    reword the email description comment)
  - `src/features/email/composition/settings.py` (remove `resend_*`
    fields/kwargs/assignments, narrow `EmailBackend` + the guard,
    remove the `validate()` resend branch and the now-dead
    `resolved_from_address()`, reword `validate_production`)
  - `src/features/email/composition/container.py` (remove the `resend` arm,
    the deferred `httpx`-guarded import, and the module-level extra comment)
  - `.env.example` (remove two `APP_EMAIL_RESEND_*` keys + comment, reword the
    email comment)
  - `pyproject.toml` (remove the `resend` extra + comment block, the
    `uv sync --extra resend` install-modes line, and the `dev`-group
    `httpx>=0.28.1` and `respx>=0.21` entries — see httpx audit)
  - `uv.lock` (regenerate via `uv lock` after the `pyproject.toml` edits)
  - **No edit to the three composition call sites** (`src/main.py`,
    `src/worker.py`, `src/cli/create_super_admin.py`) or
    `src/features/authentication/tests/e2e/conftest.py`: audited — none of
    them ever passed `resend_*` kwargs to `EmailSettings.from_app_settings`
    (they pass only `backend`/`from_address`/`console_log_bodies`). This
    differs from the SMTP removal, where eight `smtp_*` kwargs were forwarded
    at each site.
- **httpx audit conclusion**: `httpx` appears in `pyproject.toml` in four
  roles. (1) The `resend = ["httpx>=0.28.1"]` extra — **removed** (sole
  purpose was the Resend adapter). (2) The `dev` group `httpx>=0.28.1` and
  `respx>=0.21` — **removed**: a repo-wide search for `import httpx` /
  `httpx.` / `import respx` / `respx.` in `src/` returns exactly four files —
  the Resend adapter, its unit test, the contract test (de-parametrised here,
  losing its httpx/respx imports), and
  `test_configure_tracing.py` (which only *patches the string*
  `"opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor"` and never
  imports `httpx`). After this change nothing in `src/` imports `httpx` or
  `respx`, so the dev test deps go. (3) `opentelemetry-instrumentation-httpx`
  in `[project] dependencies` (runtime) — **kept**: it is an OTel auto-
  instrumentor toggled by `APP_OTEL_INSTRUMENT_HTTPX`; it does not require
  `httpx` to be importable (the instrumentor no-ops if httpx is absent) and
  removing it is observability scope (ROADMAP-unrelated), not Resend scope.
  Conservative call: leave it. (4) `"httpx"` at `pyproject.toml` lines ~332 /
  ~357 / ~408 — these are **Import Linter `forbidden_modules` entries**, not
  dependency declarations: they assert "domain/application MUST NOT import
  httpx". They are architectural guardrails that stay valid (and cheap)
  regardless of whether httpx is installed; removing them would silently
  weaken a layering contract. **Kept, untouched.**
- **Tests**:
  - Delete `src/features/email/tests/unit/test_resend_adapter.py`.
  - De-parametrise `src/features/email/tests/contracts/test_email_port_contract.py`
    (drop `resend` factory/id/fixture/constant + httpx/respx/Resend imports;
    keep `console` + `fake`; drop the unused `resend_mock` param).
  - In `src/app_platform/tests/test_settings.py`: repoint `_VALID_PROD_ENV`
    from `resend` to `console` (drop `APP_EMAIL_RESEND_API_KEY`); delete the
    three `resend`-specific tests; ensure a test asserts production refuses
    `console` with a message naming no removed backend; isolate the
    now-always-present email-backend error in the other production-refusal
    tests so each still asserts its own target.
  - Edit `src/app_platform/tests/unit/observability/test_configure_tracing.py`
    (`test_production_ratio_one_emits_warning`: `email_backend="resend"` +
    `email_resend_api_key` → `email_backend="console"`).
- **Migrations**: none. No table, column, index, or persisted state is
  touched. Resend was a runtime HTTP dispatch path with zero database
  footprint. (`AppSettings.model_config` uses `extra="ignore"`, so any stale
  `APP_EMAIL_RESEND_*` env var in a deployed environment is silently ignored —
  no compatibility shim is required.)
- **Docs** (Resend lines only — no wholesale rewrite; steps 9/10/11 own that):
  `docs/email.md`, `docs/operations.md`, `docs/architecture.md`, `README.md`,
  `CLAUDE.md`, `CONTRIBUTING.md` (corrected a stale `test(email): add Resend
  retry contract` commit-subject example and a now-invalid
  `Email backend is \`resend\`…` pre-deploy checklist item that named the
  removed `resend` backend; the unrelated English-verb "resend" slugs in the
  commit/branch examples are left untouched). The earlier audit note that
  `CONTRIBUTING.md` contained only the unrelated verb was wrong — a re-audit
  found these two real Resend-adapter references.
- **Production behavior**: the production validator already refused `console`
  and accepted only `{resend}`. It now refuses `console` and accepts **no**
  email backend — production-with-email is not bootable until ROADMAP step 25
  ships `aws_ses`. Any deployment running `APP_EMAIL_BACKEND=resend` now fails
  fast at startup with "unknown backend" (intended — Resend is gone). This is
  the honest mid-cleanup state of an AWS-first starter, not a silent
  regression; see "Key decision" for the rejected alternative (relaxing the
  refusal) and why it is unsafe.
- **Quality gate**: `make quality` and `make test` MUST stay green after the
  removal. The email contract suite MUST still pass for `console` and `fake`.
  Removing the adapter, its test, its contract parametrisation, its dependency
  extra, the dev httpx/respx deps, and its config surface together keeps the
  suite and the Import Linter contracts consistent.

## Out of scope (do NOT touch)

- The `console` adapter (`src/features/email/adapters/outbound/console/`) — it
  is the dev/test default and the only surviving email adapter.
- The future AWS SES adapter and any AWS/SES code or config — ROADMAP step 25.
  Do not add a `ses` extra, an `aws_ses` backend value, or an SES accept-path
  to the validator here.
- The `docs/operations.md` "production refuses to start if…" narrative
  reconciliation — ROADMAP step 11. Only delete Resend lines and state the
  minimal accurate post-removal reality.
- Any broader rewrite of `README.md` or `CLAUDE.md` beyond deleting Resend
  lines / restating the email row honestly — ROADMAP steps 9/10.
- The `opentelemetry-instrumentation-httpx` runtime dependency and the
  `APP_OTEL_INSTRUMENT_HTTPX` toggle / its tests — observability scope,
  ROADMAP-unrelated, and not forced by Resend removal (the instrumentor
  no-ops without httpx installed).
- The `"httpx"` Import Linter `forbidden_modules` entries in `pyproject.toml`
  — architectural guardrails, valid regardless of installed deps.

This change is strictly ROADMAP ETAPA I step 4. It does not advance steps 5–12
(arq/SpiceDB/S3 removal, api.md, README/CLAUDE/operations rewrites, cli docs)
or any ETAPA II+ work.
