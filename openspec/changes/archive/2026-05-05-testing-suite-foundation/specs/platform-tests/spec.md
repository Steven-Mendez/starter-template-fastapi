## ADDED Requirements

### Requirement: Problem+JSON handler tests

`src/platform/tests/test_problem_details.py` MUST verify that the platform's exception handlers emit RFC 9457-compliant payloads for: validation errors (HTTP 422), Starlette HTTPException, application HTTPException (with `code` and `type_uri`), `DependencyContainerNotReadyError` (HTTP 503), and unhandled exceptions (HTTP 500). Each test MUST assert media type `application/problem+json`, the presence of mandatory fields (`type`, `title`, `status`, `instance`), and the request id propagation.

#### Scenario: Validation error
- **WHEN** a request body fails Pydantic validation
- **THEN** the response is HTTP 422 with media type `application/problem+json` and body containing `errors` (the Pydantic error list)

#### Scenario: Container not ready
- **WHEN** the API receives a request before the lifespan has set the container
- **THEN** the response is HTTP 503 with `code = "dependency_container_not_ready"`

### Requirement: Request id middleware tests

`src/platform/tests/test_request_context_middleware.py` MUST verify that: when a request lacks `X-Request-ID`, the middleware generates one and sets it both on `request.state.request_id` and on the response header `X-Request-ID`; when the header is provided, the middleware echoes it unchanged; the middleware logs a JSON line per request containing `request_id`, `method`, `path`, `status_code`, and `duration_ms`.

#### Scenario: Header echoed when present
- **WHEN** a request includes `X-Request-ID: abc-123`
- **THEN** the response header `X-Request-ID` equals `abc-123`

#### Scenario: Header generated when missing
- **WHEN** a request omits `X-Request-ID`
- **THEN** the response header `X-Request-ID` is a non-empty UUID-shaped string

### Requirement: App lifespan tests

`src/platform/tests/test_app_lifespan.py` MUST verify that: `build_platform` is called exactly once per app startup; `register_kanban` is invoked during lifespan; `app.state.container` is populated before the first request; the platform shutdown hook is invoked on teardown; and `app.state.container` is cleared after teardown.

#### Scenario: Container set on startup, cleared on teardown
- **WHEN** the app's lifespan completes startup and then teardown
- **THEN** `app.state.container` is non-None during the active period and falsy afterwards

### Requirement: Settings tests

`src/platform/tests/test_settings.py` MUST verify that `AppSettings` resolves environment variables prefixed with `APP_`, parses list-typed fields (`cors_origins`, `trusted_hosts`) from JSON, defaults `enable_docs` to True in development, and rejects invalid `environment` values.

#### Scenario: Env override
- **WHEN** `APP_ENVIRONMENT=production` is set
- **THEN** `get_settings().environment == "production"` and `enable_docs` defaults to False
