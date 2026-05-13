## ADDED Requirements

### Requirement: Structured logs redact known sensitive keys

The structlog processor chain and the root stdlib logger SHALL apply a redaction step that operates on **key names only** (no value-scanning, no regex over message strings). Key matching SHALL be case-insensitive.

The redaction sets are fixed:

- **Strict redaction** (value replaced with `***REDACTED***`):
  `password`, `password_hash`, `hash`, `token`, `access_token`, `refresh_token`,
  `authorization`, `cookie`, `set-cookie`, `secret`, `api_key`, `phone`.
- **Email masking** (value rewritten by `redact_email(...)` to the form `f***@domain`):
  `email`, `to`, `from`, `recipient`, `cc`, `bcc`.
- **Header deny-list** (applied to any nested `headers`, `request.headers`, or `response.headers` mapping; strict treatment):
  `authorization`, `cookie`, `set-cookie`, `proxy-authorization`, `x-api-key`, `x-auth-token`.

The strict and email rules SHALL also apply inside header mappings.

#### Scenario: Password key is redacted

- **GIVEN** a log call with `extra={"password": "hunter2"}`
- **WHEN** the record is emitted
- **THEN** the rendered line contains `password=***REDACTED***`
- **AND** the line does NOT contain `hunter2`

#### Scenario: Email key is masked

- **GIVEN** a log call with `extra={"email": "foo@bar.com"}`
- **WHEN** the record is emitted
- **THEN** the rendered line contains `email=f***@bar.com`

#### Scenario: Authorization header is redacted regardless of case

- **GIVEN** a log call with `extra={"headers": {"Authorization": "Bearer xyz"}}`
- **WHEN** the record is emitted
- **THEN** the rendered headers mapping shows `Authorization=***REDACTED***`
- **AND** the line does NOT contain `Bearer xyz`

#### Scenario: Non-listed keys pass through unchanged

- **GIVEN** a log call with `extra={"user_id": "u-123", "duration_ms": 42}`
- **WHEN** the record is emitted
- **THEN** the rendered line preserves both values verbatim

#### Scenario: Redaction fails closed on malformed email value

- **GIVEN** a log call with `extra={"email": "not-an-email"}` (no `@`)
- **WHEN** the record is emitted
- **THEN** the rendered line shows the `email` key replaced with `***REDACTED***` (NOT the raw `not-an-email` string)
- **AND** the line contains no substring of the original value

#### Scenario: Redaction fails closed when value is non-string

- **GIVEN** a log call with `extra={"token": {"nested": "abc"}}` or `extra={"password": 12345}`
- **WHEN** the record is emitted
- **THEN** the rendered line replaces the value with `***REDACTED***`
- **AND** the original payload is not rendered (no `abc`, no `12345`)

#### Scenario: Redaction processor raises does not emit raw record

- **GIVEN** an event whose value triggers an unexpected exception inside the processor (e.g. an object whose `__str__` raises)
- **WHEN** the record is emitted
- **THEN** the emitted line for that key is `***REDACTED***` (fail-closed)
- **AND** the original value never appears in the output

### Requirement: Email adapters do not log message bodies or raw recipient addresses

Every email adapter (`console`, `smtp`, `resend`) SHALL log recipient addresses only through `redact_email(...)`. The console adapter SHALL log the rendered body as `body_len=<n> body_sha256=<hex>`; the full body MAY be logged only when both `APP_ENVIRONMENT=development` AND `APP_EMAIL_CONSOLE_LOG_BODIES=true`.

#### Scenario: Console adapter does not leak the reset token

- **GIVEN** a password-reset send through the console adapter with `APP_EMAIL_CONSOLE_LOG_BODIES=false`
- **WHEN** the adapter logs the dispatch
- **THEN** the captured log line contains `body_sha256=`
- **AND** does NOT contain the raw reset URL or token

#### Scenario: SMTP adapter masks the recipient

- **GIVEN** an SMTP dispatch with `to="alice@example.com"`
- **WHEN** the adapter logs the dispatch
- **THEN** the captured log line contains `to=a***@example.com`

#### Scenario: SMTP error path also redacts the recipient

- **GIVEN** an SMTP dispatch where `_dispatch(envelope)` raises `smtplib.SMTPException`
- **WHEN** the adapter logs `event=email.smtp.failed`
- **THEN** the captured error log line contains `to=a***@example.com`
- **AND** the line does NOT contain `alice@example.com`

#### Scenario: Console body-bypass requires both flag and dev environment

- **GIVEN** `APP_EMAIL_CONSOLE_LOG_BODIES=true` and `APP_ENVIRONMENT=staging`
- **WHEN** the console adapter sends a password-reset
- **THEN** the captured log line contains `body_sha256=` and NOT the raw body
- **AND** the bypass is only honored when both `APP_EMAIL_CONSOLE_LOG_BODIES=true` AND `APP_ENVIRONMENT=development` hold

### Requirement: Access logs include the request_id

The access log line for every HTTP request SHALL include the same `request_id` that `RequestContextMiddleware` sets on the response. uvicorn's default access logger SHALL be disabled; a Starlette `AccessLogMiddleware` mounted **after** `RequestContextMiddleware` SHALL emit the access line so the contextvar is already populated.

#### Scenario: Access log emits request_id

- **GIVEN** a request to `/me`
- **WHEN** the response is sent
- **THEN** the captured access log line contains a non-empty `request_id`
- **AND** the value matches the response's `X-Request-ID` header

#### Scenario: Default uvicorn access logger is silent

- **GIVEN** uvicorn's `uvicorn.access` logger
- **WHEN** the application is started with the configured logging chain
- **THEN** that logger is disabled (or its level is above `INFO`)
- **AND** no access line is emitted twice (only `AccessLogMiddleware`'s line is captured)
