## ADDED Requirements

### Requirement: Every route declares its 4xx responses in OpenAPI

Every HTTP route SHALL declare the relevant 4xx responses (at minimum 401, 422, and 429 where applicable) via FastAPI's `responses={}` mechanism, using the shared `ProblemDetails` Pydantic model. The `ProblemDetails` and `Violation` models SHALL appear in `components.schemas` of the generated OpenAPI document.

#### Scenario: OpenAPI lists error responses for `/auth/login`

- **WHEN** a test fetches `/openapi.json`
- **THEN** the entry for `POST /auth/login` declares responses for at least 401, 422, and 429
- **AND** each error response references `#/components/schemas/ProblemDetails`

#### Scenario: ProblemDetails and Violation schemas are present

- **WHEN** a test fetches `/openapi.json`
- **THEN** `components.schemas.ProblemDetails` exists with fields `type`, `title`, `status`, `detail`, `instance`, and `violations`
- **AND** `components.schemas.Violation` exists with fields `loc`, `type`, `msg`, and `input`

#### Scenario: A route missing its declared 4xx responses is detected

- **GIVEN** a route under `/auth/*` whose decorator omits `responses=AUTH_RESPONSES`
- **WHEN** the OpenAPI presence test fetches `/openapi.json`
- **THEN** the test fails with a message naming the offending path
- **AND** the failure cites the missing status codes (subset of `{401, 422, 429}`)

### Requirement: Every route has a stable `operationId`

Every HTTP route SHALL have a stable `operationId` produced by the convention `{router_tag}_{handler_name}` in snake_case, where `router_tag` is the first entry of the router's `tags` list (or `root` if unset) and `handler_name` is the snake_case handler function name. The mapping SHALL be installed on every `APIRouter` via `generate_unique_id_function`. No two operations SHALL share the same `operationId`.

#### Scenario: operationIds follow the convention

- **WHEN** a test fetches `/openapi.json`
- **THEN** every `operationId` matches the regex `^[a-z_]+_[a-z_]+$`

#### Scenario: operationIds are unique

- **WHEN** a test collects every `operationId` across `/openapi.json`
- **THEN** the collection has no duplicates

#### Scenario: Canonical examples produced by the convention

- **WHEN** a test fetches `/openapi.json`
- **THEN** the entry for `POST /auth/login` has `operationId == "auth_login"`
- **AND** the entry for `PATCH /me` has `operationId == "users_patch_me"`
