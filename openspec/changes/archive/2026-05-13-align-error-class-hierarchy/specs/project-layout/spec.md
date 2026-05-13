## ADDED Requirements

### Requirement: All application errors descend from a common root

The project SHALL define `ApplicationError(Exception)` in `src/app_platform/shared/errors.py`. Every feature's base application error — `AuthError`, `AuthorizationError`, `EmailError`, `JobError`, `OutboxError`, `FileStorageError`, `UserError` — SHALL inherit (directly or transitively) from `ApplicationError`.

#### Scenario: Every feature base error is an ApplicationError

- **GIVEN** the loaded application
- **WHEN** test code iterates `[AuthError, AuthorizationError, EmailError, JobError, OutboxError, FileStorageError, UserError]`
- **THEN** every entry passes `issubclass(cls, ApplicationError)`

#### Scenario: A feature base error that forgets to rebase is rejected

- **GIVEN** a hypothetical feature base error declared as `class NewFeatureError(RuntimeError)` (i.e. not rebased on `ApplicationError`)
- **WHEN** the contract test iterates the registered feature bases
- **THEN** `issubclass(NewFeatureError, ApplicationError)` returns `False`
- **AND** the test fails with a message naming `NewFeatureError`

### Requirement: `UserError` is a class hierarchy, not an Enum

`UserError` SHALL be a subclass of `ApplicationError`, with concrete subclasses `UserNotFoundError` (replacing `UserError.NOT_FOUND`) and `UserAlreadyExistsError` (replacing `UserError.DUPLICATE_EMAIL`). The users feature's HTTP error mapping SHALL dispatch by `isinstance` against these classes.

#### Scenario: UserNotFoundError is an ApplicationError

- **GIVEN** the users feature imports
- **WHEN** test code evaluates `issubclass(UserNotFoundError, UserError)` and `issubclass(UserError, ApplicationError)`
- **THEN** both return True

#### Scenario: HTTP mapping handles UserNotFoundError, not the removed enum

- **GIVEN** a `DeactivateUser` use case that resolves to `Err(UserNotFoundError())`
- **WHEN** the users-feature HTTP error mapping dispatches the error
- **THEN** the mapping returns a 404 Problem Details response
- **AND** the mapping does not attempt to compare against any `UserError.NOT_FOUND` enum value

### Requirement: All concrete `ApplicationError` subclasses are picklable

Every concrete subclass of `ApplicationError` SHALL round-trip cleanly through `pickle`: `pickle.loads(pickle.dumps(err))` MUST produce an instance of the same type whose `str()` equals the original's `str()`. Subclasses whose constructor requires non-positional arguments MUST implement `__reduce__` to satisfy the contract.

#### Scenario: Pickle round-trip covers every ApplicationError subclass

- **GIVEN** the parametrized contract test that enumerates every concrete subclass of `ApplicationError` via recursive `__subclasses__()`
- **WHEN** each is constructed with the default `Exception(message)` shape (or its `__reduce__` is invoked when the constructor requires more) and round-tripped through `pickle`
- **THEN** the round-tripped exception has the same type and the same `str()` as the original
- **AND** the test fails with a clear message naming any subclass whose constructor signature blocks the round-trip
