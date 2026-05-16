## Why

ROADMAP ETAPA I step 2 ("dejar el repo honesto"): remove configuration surface
that promises a capability the system does not have. The `APP_AUTH_OAUTH_*`
env vars are placeholders for a Google-OAuth login flow that was never
implemented. Today they:

1. **Lie in the public config contract.** `.env.example` ships four
   `APP_AUTH_OAUTH_*` keys and `docs/operations.md` documents them twice (a
   prose "OAuth Preparation" section and a four-row env-var reference table) as
   if they were live tunables. An operator reading the env reference cannot
   tell that setting `APP_AUTH_OAUTH_ENABLED=true` does nothing.
2. **Carry dead code through every layer.** Four fields on `AppSettings`, four
   mirrored fields on the `AuthenticationSettings` projection (plus their
   `from_app_settings` assignments), a `_warn_unused_oauth_settings` function
   and its call site in the auth container, and an integration test that exists
   only to assert that warning fires. The warning is the tell: a setting whose
   sole runtime behavior is to log "this setting does nothing" is dead config.
3. **Confuse the later federated-identity work.** ROADMAP steps 5/15 introduce
   real federated identity via Cognito (Opción B: `identities` table, local
   credentials coexist). That work will design its own config surface from
   scratch. Leaving a half-named Google-OAuth scaffold around invites someone
   to "reuse" it and inherit a shape that was never validated.

This step deletes the dead Google-OAuth env scaffolding only. It does not
design, add, or redesign any authentication or federated-identity behavior —
that is explicitly later ROADMAP work.

## What Changes

- Remove the four `APP_AUTH_OAUTH_*` keys (and their dedicated comment/header,
  if any) from `.env.example`.
- Remove the four `auth_oauth_*` fields and their `# TODO: OAuth ...` comment
  from `AppSettings` (`src/app_platform/config/settings.py`).
- Remove the four `oauth_*` fields from the `AuthenticationSettings` dataclass
  and the four matching `oauth_*=app.auth_oauth_*` assignments in its
  `from_app_settings` factory (`src/features/authentication/composition/settings.py`).
- Remove the `_warn_unused_oauth_settings` function **and** its call site in
  `build_auth_container` (`src/features/authentication/composition/container.py`).
- Delete the `test_build_auth_container_warns_for_unimplemented_oauth_settings`
  integration test — the behavior it pins is being removed, so the test must go
  with it (no replacement: there is no longer anything to assert).
- Remove both OAuth doc sites from `docs/operations.md`: the `### OAuth
  Preparation` prose section and the four `APP_AUTH_OAUTH_*` rows in the
  env-var reference table.

**Production-validator audit (required by the ROADMAP item):** neither
`AuthenticationSettings.validate_production` nor `AppSettings.validate_production`
contains any OAuth-related entry. The OAuth fields were never wired into
production validation — their only runtime behavior was the startup warning
being removed above. No validator change is needed; this proposal records the
audit result so a reviewer does not have to re-derive it.

**Capabilities — Modified**
- `authentication`: the production-validator-surface requirement is tightened
  so the validator/settings surface may not carry placeholder config for
  unimplemented features.

**Capabilities — New**
- None.

## Impact

- **Code**:
  - `.env.example` (remove four keys + their comment block)
  - `src/app_platform/config/settings.py` (remove four fields + TODO comment)
  - `src/features/authentication/composition/settings.py` (remove four
    dataclass fields + four factory assignments)
  - `src/features/authentication/composition/container.py` (remove
    `_warn_unused_oauth_settings` + its call site)
  - `docs/operations.md` (remove `### OAuth Preparation` section + four
    env-table rows)
- **Tests**: delete
  `test_build_auth_container_warns_for_unimplemented_oauth_settings` in
  `src/features/authentication/tests/integration/test_auth_container_rate_limiter.py`.
  No new tests — this change removes dead code, it does not add behavior.
- **Migrations**: none. No table, column, or persisted state is touched.
- **Production behavior**: none. The removed fields had no effect beyond a
  startup log line. Operators currently setting `APP_AUTH_OAUTH_*` get no
  behavior change (the values were ignored); the env vars become unknown keys,
  which `pydantic-settings` ignores by default (extra env vars are not an
  error) — confirm during implementation if `model_config` sets
  `extra="forbid"`.
- **Quality gate**: `make test` and `make quality` MUST stay green after the
  removal. The deleted integration test is the only test referencing this
  surface; removing the code and the test together keeps the suite consistent.

## Out of scope (do NOT touch)

These are legitimate, unrelated uses of the word "oauth" and must be left
exactly as they are. They are forward-looking comments or standards-compliant
naming, not dead Google-OAuth scaffolding:

- `token_type="bearer"` / OAuth-style bearer-token comments in
  `application/use_cases/auth/login_user.py`, `.../refresh_token.py`,
  the auth HTTP `schemas.py`, and `application/types.py`.
- The `OAuth2PasswordBearer` explanatory comment in
  `src/features/authentication/adapters/inbound/http/dependencies.py`.
- The `/docs/oauth2-redirect` Swagger path in `security_headers.py` and its
  test `test_security_headers.py` (this is the Swagger UI redirect, unrelated
  to login OAuth) — also referenced by the `project-layout` spec's CSP
  requirement, which stays untouched.
- The "OAuth-link rows can join later" / SSO forward-looking comments in
  `domain/models.py`, the auth `adapters/.../sqlmodel/models.py`, and
  `docs/architecture.md:251` ("the `credentials` table is shaped to support
  it"). These describe a deliberately extensible schema for the *future*
  Cognito work and are not part of this cleanup.

This change is strictly ROADMAP ETAPA I step 2. It does not advance steps 3–7
(SMTP/Resend/arq/SpiceDB/S3 removal) or any ETAPA II+ federated-identity work.
