## MODIFIED Requirements

### Requirement: Email backend selection

`build_email_container` SHALL instantiate exactly one adapter based on `EmailSettings.backend` (`console` or `resend`), expose it on the returned `EmailContainer.port`, and SHALL fail fast with `RuntimeError` if backend-specific required settings are absent.

#### Scenario: Resend backend without API key fails fast

- **GIVEN** `EmailSettings(backend="resend", resend_api_key=None, ...)`
- **WHEN** `build_email_container(settings)` is called
- **THEN** the call raises `RuntimeError` whose message names `APP_EMAIL_RESEND_API_KEY`

#### Scenario: Console backend builds without provider settings

- **GIVEN** `EmailSettings(backend="console", resend_api_key=None, ...)`
- **WHEN** `build_email_container(settings)` is called
- **THEN** the call returns an `EmailContainer` whose port is a `ConsoleEmailAdapter`

#### Scenario: An unknown backend value is rejected at settings construction

- **GIVEN** an attempt to build `EmailSettings` with `backend="smtp"`
- **WHEN** `EmailSettings.from_app_settings(backend="smtp")` is called
- **THEN** the call raises `ValueError` whose message lists the allowed backends `'console'` and `'resend'` and does NOT list `'smtp'`

### Requirement: Production settings validator

The settings validator SHALL refuse `APP_EMAIL_BACKEND=console` when `APP_ENVIRONMENT=production`. It SHALL accept `resend` provided its required fields are set. It SHALL require `APP_EMAIL_RESEND_API_KEY` and `APP_EMAIL_FROM` when `APP_EMAIL_BACKEND=resend`, in every environment. `APP_EMAIL_BACKEND` SHALL accept only `console` or `resend`; any other value SHALL fail validation.

#### Scenario: Console backend rejected in production

- **GIVEN** `APP_ENVIRONMENT=production` and `APP_EMAIL_BACKEND=console`
- **WHEN** `AppSettings` is constructed
- **THEN** validation raises `ValueError` whose message lists the email-backend mismatch
- **AND** the message does NOT instruct the operator to configure `smtp`

#### Scenario: Resend backend without API key rejected in any environment

- **GIVEN** `APP_EMAIL_BACKEND=resend` and `APP_EMAIL_RESEND_API_KEY` unset
- **WHEN** `AppSettings` is constructed
- **THEN** validation raises `ValueError` whose message names `APP_EMAIL_RESEND_API_KEY`

#### Scenario: Resend backend with API key and From address is accepted in production

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_EMAIL_BACKEND=resend`, `APP_EMAIL_RESEND_API_KEY=...`, and `APP_EMAIL_FROM=no-reply@example.com`
- **WHEN** `AppSettings` is constructed
- **THEN** validation passes

#### Scenario: The smtp backend value is no longer accepted

- **GIVEN** `APP_EMAIL_BACKEND=smtp`
- **WHEN** `AppSettings` is constructed
- **THEN** validation raises an error rejecting the unknown backend value
- **AND** no `APP_EMAIL_SMTP_*` field exists on `AppSettings`
