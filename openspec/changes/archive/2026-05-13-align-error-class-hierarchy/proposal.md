## Why

Three related inconsistencies:

1. **No common `ApplicationError` root.** CLAUDE.md describes `Result[T, ApplicationError]` as universal, but each feature defines its own base (`AuthError(RuntimeError)`, `AuthorizationError(RuntimeError)`, `OutboxError(Exception)`, `EmailError(Exception)`, `JobError(Exception)`, `FileStorageError(Exception)`). They don't share an ancestor.
2. **`UserError` is an `Enum`, not an exception hierarchy** (`src/features/users/application/errors.py:8` — closed enum with values `DUPLICATE_EMAIL` and `NOT_FOUND`). Diverges from every sibling feature.
3. **Cross-process pickling not validated.** arq pickles exceptions across the Redis boundary. Errors with custom `__init__` signatures requiring kwargs can break `Exception.__reduce__`. Today no concrete subclass takes kwargs, but `RateLimitExceededError` is about to gain `retry_after_seconds: int` (`preserve-error-response-headers` change); a contract test now prevents future regressions.

## What Changes

- Introduce `ApplicationError(Exception)` in `src/app_platform/shared/errors.py`.
- Have every feature's base exception inherit from it: `AuthError`, `AuthorizationError`, `EmailError`, `JobError`, `OutboxError`, `FileStorageError`, `UserError`.
- Convert `UserError` from `Enum` to a hierarchy: `UserError(ApplicationError)` with one subclass per existing enum value: `UserNotFoundError` (replaces `UserError.NOT_FOUND`) and `UserAlreadyExistsError` (replaces `UserError.DUPLICATE_EMAIL`). No new error cases — that's a separate change. (The auth feature already owns `InactiveUserError(AuthError)` for the "request targets an inactive user" case; a `UserDeactivatedError` would duplicate it without adding signal.)
- Migrate the users feature's HTTP error mapping (`src/features/users/adapters/inbound/http/errors.py`) from enum matching to `isinstance` matching.
- Add a parametrized contract test that walks `ApplicationError.__subclasses__()` recursively and `pickle.dumps`/`loads` round-trips every concrete subclass with realistic positional args. The test fails on any subclass whose constructor requires kwargs that `Exception.__reduce__` cannot serialize.

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code (edit)**:
  - `src/app_platform/shared/errors.py` (add `ApplicationError`).
  - `src/features/authentication/application/errors.py` (rebase `AuthError` on `ApplicationError`).
  - `src/features/authorization/application/errors.py` (rebase `AuthorizationError`).
  - `src/features/email/application/errors.py` (rebase `EmailError`).
  - `src/features/background_jobs/application/errors.py` (rebase `JobError`).
  - `src/features/outbox/application/errors.py` (rebase `OutboxError`).
  - `src/features/file_storage/application/errors.py` (rebase `FileStorageError`).
  - `src/features/users/application/errors.py` (replace `Enum` with class hierarchy).
  - `src/features/users/application/use_cases/deactivate_user.py:26` (`Err(UserError.NOT_FOUND)` → `Err(UserNotFoundError())`); audit other use cases for `UserError.DUPLICATE_EMAIL` / `UserError.NOT_FOUND` references with `rg "UserError\."` and update each.
  - `src/features/users/adapters/inbound/http/errors.py` (switch from enum matching to `isinstance` matching).
  - `CLAUDE.md` ("Coding conventions" section).
- **Code (new)**:
  - `src/app_platform/shared/tests/unit/test_application_error_pickling.py` (parametrized pickle round-trip).
- **CI**: new round-trip test enforces the invariant.
- **Backwards compatibility**: internal — only consumers of `UserError` enum values inside the codebase need to update; the public HTTP contract is unchanged.
