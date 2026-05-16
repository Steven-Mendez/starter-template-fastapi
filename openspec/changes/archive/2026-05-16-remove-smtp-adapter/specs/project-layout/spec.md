## MODIFIED Requirements

### Requirement: Email adapters do not log message bodies or raw recipient addresses

Every email adapter (`console`, `resend`) SHALL log recipient addresses only through `redact_email(...)`. The console adapter SHALL log the rendered body as `body_len=<n> body_sha256=<hex>`; the full body MAY be logged only when both `APP_ENVIRONMENT=development` AND `APP_EMAIL_CONSOLE_LOG_BODIES=true`.

#### Scenario: Console adapter does not leak the reset token

- **GIVEN** a password-reset send through the console adapter with `APP_EMAIL_CONSOLE_LOG_BODIES=false`
- **WHEN** the adapter logs the dispatch
- **THEN** the captured log line contains `body_sha256=`
- **AND** does NOT contain the raw reset URL or token

#### Scenario: Resend adapter masks the recipient

- **GIVEN** a Resend dispatch with `to="alice@example.com"`
- **WHEN** the adapter logs the dispatch
- **THEN** the captured log line contains `to=a***@example.com`
- **AND** the line does NOT contain `alice@example.com`
