## 1. Root class

- [x] 1.1 Add `class ApplicationError(Exception): ...` to `src/app_platform/shared/errors.py`.
- [x] 1.2 Rebase `AuthError` (`src/features/authentication/application/errors.py`) on `ApplicationError`.
- [x] 1.3 Rebase `AuthorizationError` (`src/features/authorization/application/errors.py`) on `ApplicationError`.
- [x] 1.4 Rebase `EmailError` (`src/features/email/application/errors.py`) on `ApplicationError`.
- [x] 1.5 Rebase `JobError` (`src/features/background_jobs/application/errors.py`) on `ApplicationError`.
- [x] 1.6 Rebase `OutboxError` (`src/features/outbox/application/errors.py`) on `ApplicationError`.
- [x] 1.7 Rebase `FileStorageError` (`src/features/file_storage/application/errors.py`) on `ApplicationError`.

## 2. UserError refactor

- [x] 2.1 Rewrite `src/features/users/application/errors.py`:
  - [x] 2.1.a Remove the `Enum` import and the `UserError(Enum)` declaration.
  - [x] 2.1.b Declare `class UserError(ApplicationError)` as the feature base.
  - [x] 2.1.c Declare `class UserNotFoundError(UserError)` and `class UserAlreadyExistsError(UserError)`. No `UserDeactivatedError` — the auth feature already owns `InactiveUserError` for that semantic.
- [x] 2.2 Run `rg "UserError\."` and update every hit. Confirmed: `src/features/users/application/use_cases/deactivate_user.py:26` (`Err(UserError.NOT_FOUND)` → `Err(UserNotFoundError())`). Sweep for any other use cases that may have been added since.
- [x] 2.3 Update `src/features/users/adapters/inbound/http/errors.py` to dispatch by `isinstance` against `UserNotFoundError` / `UserAlreadyExistsError` instead of matching enum values. (Mapping lives inline in `me.py`; switched to `isinstance` there.)

## 3. Pickling contract

- [x] 3.1 Add `src/app_platform/shared/tests/unit/test_application_error_pickling.py`.
  - [x] 3.1.a Define a `_all_subclasses(cls)` recursive helper that yields every transitive subclass.
  - [x] 3.1.b Build the parametrize list by walking `ApplicationError.__subclasses__()` recursively and excluding the per-feature abstract bases (`AuthError`, `AuthorizationError`, `EmailError`, `JobError`, `OutboxError`, `FileStorageError`, `UserError`).
  - [x] 3.1.c For each concrete leaf, construct with `cls("msg")` (default `Exception` shape); when the constructor requires more, surface a clear `pytest.fail(...)` naming the class.
  - [x] 3.1.d Assert `pickle.loads(pickle.dumps(err))` produces an instance of the same type and that `str(loaded) == str(err)`.
- [x] 3.2 For any class whose constructor requires kwargs (none today, but `RateLimitExceededError` is about to gain `retry_after_seconds: int` from `preserve-error-response-headers`), implement `__reduce__` returning `(cls, (positional_args,))` so the round-trip test passes. Document the rule in the test docstring so future contributors see it.

## 4. Wrap-up

- [x] 4.1 Update CLAUDE.md "Coding conventions" with the unified hierarchy and the picklability requirement.
- [x] 4.2 Run `make ci` and confirm green.
