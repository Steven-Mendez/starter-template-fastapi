## ADDED Requirements

### Requirement: Email is a self-contained feature slice

The system SHALL host transactional-email concerns in a dedicated feature slice at `src/features/email/`. The slice SHALL contain the `EmailPort` inbound port, the `console` and `smtp` adapters, a template-rendering helper, and the registry through which other features contribute their email templates. The slice SHALL NOT contain authentication, user, or authorization logic.

#### Scenario: Email owns its port and adapters

- **WHEN** the codebase is loaded
- **THEN** `src/features/email/application/ports/email_port.py` defines `EmailPort` as a Protocol with a single method `send(to, template_name, context)`
- **AND** `src/features/email/adapters/outbound/console/` and `src/features/email/adapters/outbound/smtp/` each contain an adapter that implements `EmailPort`

#### Scenario: Email does not import from other features

- **WHEN** the codebase is loaded
- **THEN** no module under `src/features/email/` imports from any other `src/features/<name>/` directory

### Requirement: The active adapter is selected by configuration

The system SHALL select the email adapter at startup from `APP_EMAIL_BACKEND`, which accepts the values `console` or `smtp`. When the value is `console`, the console adapter SHALL be wired. When the value is `smtp`, the smtp adapter SHALL be wired and `APP_EMAIL_SMTP_HOST`, `APP_EMAIL_SMTP_PORT`, `APP_EMAIL_FROM` SHALL be required. Production validation SHALL refuse `console` when `APP_ENVIRONMENT=production`.

#### Scenario: Console adapter is selected in development

- **GIVEN** `APP_EMAIL_BACKEND=console` and `APP_ENVIRONMENT=development`
- **WHEN** the application starts
- **THEN** `EmailPort` resolves to the console adapter
- **AND** calling `EmailPort.send(...)` writes a structured log line containing `to`, `template_name`, and the rendered body

#### Scenario: Production refuses the console adapter

- **GIVEN** `APP_EMAIL_BACKEND=console` and `APP_ENVIRONMENT=production`
- **WHEN** the application starts
- **THEN** startup fails with a settings validation error naming `APP_EMAIL_BACKEND`

#### Scenario: SMTP adapter requires host, port, and from

- **GIVEN** `APP_EMAIL_BACKEND=smtp` and `APP_EMAIL_SMTP_HOST` is unset
- **WHEN** the application starts
- **THEN** startup fails with a settings validation error naming the missing variable

### Requirement: Features register their templates with the email feature

Each feature that sends email SHALL register its template files with the email feature at composition time via an `EmailTemplateRegistry`. The registry SHALL be sealed before the application starts serving traffic. The email feature SHALL refuse to send a template that was never registered.

#### Scenario: Authentication registers password-reset and verify-email templates

- **WHEN** `build_authentication_container(...)` returns
- **THEN** the email template registry contains entries for `authentication/password_reset` and `authentication/verify_email`
- **AND** each entry resolves to a Jinja2 template file under `src/features/authentication/email_templates/`

#### Scenario: Sending an unregistered template fails

- **WHEN** `EmailPort.send(to="...", template_name="does-not-exist", context={})` is called
- **THEN** the call returns `Err(UnknownTemplateError)`
- **AND** no message is sent

### Requirement: Password-reset and verify-email flows use EmailPort

The `RequestPasswordReset` and `RequestEmailVerification` use cases SHALL render their email via the email template registry and enqueue a `SendEmailJob` (see `background-jobs`) with the rendered payload. Neither use case SHALL return the single-use token in its response body, except when `APP_AUTH_RETURN_INTERNAL_TOKENS=true` (test-only; forbidden in production).

#### Scenario: Password-reset response no longer contains the token

- **GIVEN** `APP_AUTH_RETURN_INTERNAL_TOKENS=false`
- **WHEN** a client calls `POST /auth/password-reset` with a valid email
- **THEN** the response status is 202
- **AND** the response body contains no `token` field
- **AND** a `SendEmailJob` has been enqueued whose payload includes the rendered email

#### Scenario: Test mode still exposes the token

- **GIVEN** `APP_AUTH_RETURN_INTERNAL_TOKENS=true` and `APP_ENVIRONMENT=development`
- **WHEN** a client calls `POST /auth/password-reset` with a valid email
- **THEN** the response body contains a `token` field
- **AND** the production validator refuses to start with this combination when `APP_ENVIRONMENT=production`
