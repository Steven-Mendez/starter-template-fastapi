# email Specification

## Purpose
TBD - created by archiving change add-s3-and-resend-adapters. Update Purpose after archive.
## Requirements
### Requirement: EmailPort contract

The system SHALL expose an `EmailPort` Protocol in `src.features.email.application.ports.email_port` with a single method `send(*, to: str, template_name: str, context: dict[str, Any]) -> Result[None, EmailError]`. Adapters SHALL render the template via the wired `EmailTemplateRegistry` and SHALL NOT raise application-level errors through `send`; failure paths SHALL be returned as `Err(EmailError-subclass)` values.

#### Scenario: Sending a registered template returns Ok

- **GIVEN** a wired `EmailPort` whose registry has a template `"contract/msg"` with subject `"hi"` and body `"Hi {{ name }}\n"`
- **WHEN** `port.send(to="a@example.com", template_name="contract/msg", context={"name": "A"})` is called
- **THEN** the call returns `Ok(None)`

#### Scenario: Sending an unregistered template returns Err

- **GIVEN** a wired `EmailPort` whose registry does not contain `"never-registered"`
- **WHEN** `port.send(to="a@example.com", template_name="never-registered", context={})` is called
- **THEN** the call returns `Err(UnknownTemplateError(template_name="never-registered"))`

### Requirement: EmailTemplateRegistry seal lifecycle

The `EmailTemplateRegistry` SHALL accept template registrations until `seal()` is called, and SHALL raise on any registration attempt after sealing. It SHALL reject duplicate template names. The composition root SHALL call `seal()` after every feature has contributed its templates and before the application accepts traffic.

#### Scenario: Duplicate registration raises

- **GIVEN** a fresh `EmailTemplateRegistry`
- **WHEN** `register_template("welcome", subject="...", body_path=path)` is called twice with the same name
- **THEN** the second call raises a registry error

#### Scenario: Registration after seal raises

- **GIVEN** an `EmailTemplateRegistry` on which `seal()` has been called
- **WHEN** `register_template("late", ...)` is called
- **THEN** the call raises a registry error

### Requirement: Resend adapter is a real HTTP implementation

The system SHALL ship `ResendEmailAdapter` at `src.features.email.adapters.outbound.resend.adapter` as a real implementation backed by `httpx`. The adapter SHALL render the template through the registry, POST a JSON body to `<base_url>/emails` with `Authorization: Bearer <api_key>`, and translate the HTTP response into a `Result`. It SHALL be selectable at composition time by setting `APP_EMAIL_BACKEND=resend`.

#### Scenario: A 2xx response returns Ok

- **GIVEN** a `ResendEmailAdapter` whose mocked transport returns HTTP 200 with body `{"id": "abc"}`
- **WHEN** `adapter.send(to="a@example.com", template_name="contract/msg", context={"name": "A"})` is called
- **THEN** the call returns `Ok(None)`
- **AND** the request payload SHALL include `"from"`, `"to": ["a@example.com"]`, `"subject"`, and `"text"` fields
- **AND** the request headers SHALL include `Authorization: Bearer <api_key>`

#### Scenario: A 4xx response returns DeliveryError

- **GIVEN** a `ResendEmailAdapter` whose mocked transport returns HTTP 422 with body `{"message": "invalid recipient"}`
- **WHEN** `adapter.send(...)` is called
- **THEN** the call returns `Err(DeliveryError(reason=...))` whose reason mentions the status code and `"invalid recipient"`

#### Scenario: A 5xx response returns DeliveryError

- **GIVEN** a `ResendEmailAdapter` whose mocked transport returns HTTP 503
- **WHEN** `adapter.send(...)` is called
- **THEN** the call returns `Err(DeliveryError(reason=...))` whose reason mentions the 5xx status
- **AND** the adapter SHALL NOT retry the request

#### Scenario: A transport failure returns DeliveryError

- **GIVEN** a `ResendEmailAdapter` whose mocked transport raises `httpx.ConnectError`
- **WHEN** `adapter.send(...)` is called
- **THEN** the call returns `Err(DeliveryError(reason=...))` whose reason carries the exception message

#### Scenario: An unknown template short-circuits without an HTTP call

- **GIVEN** a `ResendEmailAdapter` whose registry does not contain the requested template
- **WHEN** `adapter.send(to="a@example.com", template_name="missing", context={})` is called
- **THEN** the call returns `Err(UnknownTemplateError(template_name="missing"))`
- **AND** the adapter SHALL NOT issue any HTTP request

### Requirement: Email backend selection

`build_email_container` SHALL instantiate exactly one adapter based on `EmailSettings.backend` (`console`, `smtp`, or `resend`), expose it on the returned `EmailContainer.port`, and SHALL fail fast with `RuntimeError` if backend-specific required settings are absent.

#### Scenario: Resend backend without API key fails fast

- **GIVEN** `EmailSettings(backend="resend", resend_api_key=None, ...)`
- **WHEN** `build_email_container(settings)` is called
- **THEN** the call raises `RuntimeError` whose message names `APP_EMAIL_RESEND_API_KEY`

#### Scenario: SMTP backend without host fails fast

- **GIVEN** `EmailSettings(backend="smtp", smtp_host=None, ...)`
- **WHEN** `build_email_container(settings)` is called
- **THEN** the call raises `RuntimeError` whose message names `APP_EMAIL_SMTP_HOST`

#### Scenario: Console backend builds without provider settings

- **GIVEN** `EmailSettings(backend="console", smtp_host=None, resend_api_key=None, ...)`
- **WHEN** `build_email_container(settings)` is called
- **THEN** the call returns an `EmailContainer` whose port is a `ConsoleEmailAdapter`

### Requirement: Production settings validator

The settings validator SHALL refuse `APP_EMAIL_BACKEND=console` when `APP_ENVIRONMENT=production`. It SHALL accept `smtp` and `resend` provided their required fields are set. It SHALL require `APP_EMAIL_RESEND_API_KEY` and `APP_EMAIL_FROM` when `APP_EMAIL_BACKEND=resend`, in every environment.

#### Scenario: Console backend rejected in production

- **GIVEN** `APP_ENVIRONMENT=production` and `APP_EMAIL_BACKEND=console`
- **WHEN** `AppSettings` is constructed
- **THEN** validation raises `ValueError` whose message lists the email-backend mismatch

#### Scenario: Resend backend without API key rejected in any environment

- **GIVEN** `APP_EMAIL_BACKEND=resend` and `APP_EMAIL_RESEND_API_KEY` unset
- **WHEN** `AppSettings` is constructed
- **THEN** validation raises `ValueError` whose message names `APP_EMAIL_RESEND_API_KEY`

#### Scenario: Resend backend with API key and From address is accepted in production

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_EMAIL_BACKEND=resend`, `APP_EMAIL_RESEND_API_KEY=...`, and `APP_EMAIL_FROM=no-reply@example.com`
- **WHEN** `AppSettings` is constructed
- **THEN** validation passes

### Requirement: Resend base URL is configurable

The Resend adapter SHALL accept a `base_url` value sourced from `APP_EMAIL_RESEND_BASE_URL`, defaulting to `https://api.resend.com`. The adapter SHALL issue requests against `<base_url>/emails`.

#### Scenario: Custom base URL is used for the request

- **GIVEN** a `ResendEmailAdapter` constructed with `base_url="https://api.eu.resend.com"`
- **WHEN** `adapter.send(...)` is called and observed by a mocked transport
- **THEN** the captured request URL is `https://api.eu.resend.com/emails`

### Requirement: Adapters do not import from inbound or other features

No module under `src.features.email.adapters.outbound` SHALL import from `src.features.email.adapters.inbound`. No feature outside `email` SHALL import a specific adapter module; consumers SHALL depend on `EmailPort` via composition. The Resend adapter SHALL import `httpx` only within its own outbound package.

#### Scenario: Import-linter contract passes

- **WHEN** `make lint-arch` is run
- **THEN** no contract violation involving `src.features.email` is reported
