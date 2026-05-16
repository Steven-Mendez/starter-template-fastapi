## REMOVED Requirements

### Requirement: Resend adapter is a real HTTP implementation

**Reason**: ROADMAP ETAPA I step 4 removes the Resend email adapter. The
starter is AWS-first; the real production email backend is AWS SES, added at
ROADMAP step 25. The `ResendEmailAdapter`, its `httpx` dependency, and its
config surface are deleted with no replacement in this change.

**Migration**: Deployments must not set `APP_EMAIL_BACKEND=resend` — the only
accepted value is `console` (dev/test). Production email is unavailable until
ROADMAP step 25 ships `aws_ses`. Stale `APP_EMAIL_RESEND_*` env vars are
silently ignored (`AppSettings.model_config` uses `extra="ignore"`).

### Requirement: Resend base URL is configurable

**Reason**: ROADMAP ETAPA I step 4 deletes the Resend adapter; there is no
adapter to configure a base URL for. `APP_EMAIL_RESEND_BASE_URL` is removed.

**Migration**: No action — the env var is silently ignored if still set.

## MODIFIED Requirements

### Requirement: Email backend selection

`build_email_container` SHALL instantiate exactly one adapter based on `EmailSettings.backend` (`console` is the only accepted value), expose it on the returned `EmailContainer.port`, and SHALL fail fast with `RuntimeError` if an unknown backend value reaches the container. The `console` adapter is the only email backend the system ships; the production email backend (AWS SES) arrives at a later roadmap step.

#### Scenario: Console backend builds without provider settings

- **GIVEN** `EmailSettings(backend="console", ...)`
- **WHEN** `build_email_container(settings)` is called
- **THEN** the call returns an `EmailContainer` whose port is a `ConsoleEmailAdapter`

#### Scenario: An unknown backend value is rejected at settings construction

- **GIVEN** an attempt to build `EmailSettings` with `backend="resend"`
- **WHEN** `EmailSettings.from_app_settings(backend="resend")` is called
- **THEN** the call raises `ValueError` whose message lists the allowed backend `'console'` and does NOT list `'resend'` or `'smtp'`

#### Scenario: No Resend adapter module exists

- **WHEN** the codebase is loaded
- **THEN** no module exists under `src.features.email.adapters.outbound.resend`
- **AND** `build_email_container` contains no branch constructing a Resend adapter
- **AND** `EmailSettings` defines no `resend_api_key` or `resend_base_url` field

### Requirement: Production settings validator

The settings validator SHALL refuse `APP_EMAIL_BACKEND=console` when `APP_ENVIRONMENT=production`. There is no production-capable email backend until AWS SES is added at a later roadmap step, so in production the validator SHALL NOT accept any email backend value: `console` is the only accepted value and it is refused in production. `APP_EMAIL_BACKEND` SHALL accept only `console`; any other value (including `resend` or `smtp`) SHALL fail validation. The settings surface SHALL define no `email_resend_api_key` or `email_resend_base_url` field on `AppSettings`.

#### Scenario: Console backend rejected in production

- **GIVEN** `APP_ENVIRONMENT=production` and `APP_EMAIL_BACKEND=console`
- **WHEN** `AppSettings` is constructed
- **THEN** validation raises `ValueError` whose message reports the email-backend problem
- **AND** the message does NOT instruct the operator to configure `resend` or `smtp`

#### Scenario: No production email backend is accepted

- **GIVEN** `APP_ENVIRONMENT=production` and an otherwise fully-valid production environment
- **WHEN** `AppSettings` is constructed with any `APP_EMAIL_BACKEND` value
- **THEN** validation does not pass via the email-backend axis (the only accepted value, `console`, is refused in production)
- **AND** `AppSettings` defines no `email_resend_api_key` and no `email_resend_base_url` field

#### Scenario: The resend backend value is no longer accepted

- **GIVEN** `APP_EMAIL_BACKEND=resend`
- **WHEN** `AppSettings` is constructed
- **THEN** validation raises an error rejecting the unknown backend value
- **AND** no `APP_EMAIL_RESEND_*` field exists on `AppSettings`

#### Scenario: The smtp backend value is still not accepted

- **GIVEN** `APP_EMAIL_BACKEND=smtp`
- **WHEN** `AppSettings` is constructed
- **THEN** validation raises an error rejecting the unknown backend value

### Requirement: Adapters do not import from inbound or other features

No module under `src.features.email.adapters.outbound` SHALL import from `src.features.email.adapters.inbound`. No feature outside `email` SHALL import a specific adapter module; consumers SHALL depend on `EmailPort` via composition. No module under `src.features.email` SHALL import `httpx` (the only adapter that did — Resend — is removed).

#### Scenario: Import-linter contract passes

- **WHEN** `make lint-arch` is run
- **THEN** no contract violation involving `src.features.email` is reported

#### Scenario: No email module imports httpx

- **WHEN** the `src.features.email` package is searched for `import httpx`
- **THEN** no module imports `httpx`
