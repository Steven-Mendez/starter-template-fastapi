## ADDED Requirements

### Requirement: Auth use cases return Result[T, AuthError]
All auth use-case `execute()` methods SHALL return `Result[T, AuthError]` (where `Result`, `Ok`, and `Err` come from `src/platform/shared/result.py` and `AuthError` is the base class in `src/features/auth/application/errors.py`). Use cases SHALL NOT raise `AuthError` subclasses across the application boundary; they SHALL return `Err(InvalidCredentialsError(...))`, `Err(DuplicateEmailError(...))`, etc.

The existing `AuthError` subclass hierarchy (`InvalidCredentialsError`, `DuplicateEmailError`, `StaleTokenError`, `PermissionDeniedError`, ...) is preserved as-is — `Err` carries an instance of these classes; the spec does NOT introduce an enum-style `AuthError.SOME_VARIANT`.

#### Scenario: Successful registration returns Ok
- **WHEN** `RegisterUser.execute(command)` completes successfully
- **THEN** the return value is `Ok(IssuedTokens(...))`

#### Scenario: Duplicate email returns Err, not exception
- **WHEN** `RegisterUser.execute(command)` is called with an already-registered email
- **THEN** the return value is `Err(DuplicateEmailError(...))` and no exception is raised across the application boundary

#### Scenario: Invalid credentials returns Err, not exception
- **WHEN** `LoginUser.execute(command)` is called with a wrong password
- **THEN** the return value is `Err(InvalidCredentialsError(...))` and no exception is raised

#### Scenario: Expired refresh token returns Err, not exception
- **WHEN** `RefreshToken.execute(command)` is called with an expired token
- **THEN** the return value is `Err(InvalidTokenError(...))` (or a subclass) and no exception is raised

### Requirement: Auth HTTP adapters use match Ok/Err pattern
Auth HTTP adapter handlers (`auth.py`, `admin.py`) SHALL destructure `Result` using Python structural pattern matching (`match result: case Ok(v): ... case Err(e): ...`). Adapter handlers SHALL NOT use `try/except AuthError` to handle application errors. The single remaining `try/except` allowed is in `get_current_principal` while it is being migrated; it SHALL be removed once `ResolvePrincipalFromAccessTokenPort` returns `Result`.

#### Scenario: Adapter maps Ok result to HTTP success
- **WHEN** a use case returns `Ok(payload)` and the adapter processes it
- **THEN** the HTTP response has the expected success status code and the payload is serialized as the response body

#### Scenario: Adapter maps Err to HTTP error via errors.py
- **WHEN** a use case returns `Err(InvalidCredentialsError(...))`
- **THEN** the adapter calls `raise_http_from_auth_error(error)` which produces HTTP 401

#### Scenario: Unhandled Err variants are caught at type-check time
- **WHEN** a new `AuthError` subclass is added without updating `raise_http_from_auth_error`
- **THEN** mypy or the test for the error map flags the missing branch

### Requirement: Auth unit tests verify Result variants
Auth use-case unit tests SHALL assert against `Result` variants using `is_ok()` / `is_err()` helpers or structural pattern matching. Tests SHALL NOT assert by catching exceptions from use-case `execute()` calls.

#### Scenario: Unit test asserts Ok result
- **WHEN** a unit test calls `use_case.execute(valid_command)` and the use case succeeds
- **THEN** the test asserts `is_ok(result)` or `isinstance(result, Ok)`

#### Scenario: Unit test asserts Err result
- **WHEN** a unit test calls `use_case.execute(bad_command)` and the use case fails
- **THEN** the test asserts `is_err(result)` and checks `isinstance(result.error, ExpectedAuthErrorSubclass)`
