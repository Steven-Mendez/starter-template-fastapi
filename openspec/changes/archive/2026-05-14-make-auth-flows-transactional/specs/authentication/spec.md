## ADDED Requirements

### Requirement: User registration is atomic

The `RegisterUser` use case SHALL commit the new `User` row, the matching `Credential` row, and the `auth.user_registered` audit event in a single database transaction. A failure in any one of these writes MUST roll back the other two, leaving the database in the pre-registration state.

#### Scenario: Credential write failure rolls back the user row

- **GIVEN** a `RegisterUser` call with email `new@example.com` and a valid password
- **AND** the credential adapter is configured to raise on `upsert_credential` after the user row has been written
- **WHEN** the use case executes
- **THEN** the result is `Err(...)`
- **AND** a subsequent `UserPort.get_by_email("new@example.com")` returns `None`
- **AND** no audit event is recorded for that email

#### Scenario: Happy path commits once

- **GIVEN** a fresh database
- **WHEN** `RegisterUser` succeeds for email `ok@example.com`
- **THEN** exactly one transaction is committed (observable in DB logs or via a test fixture that counts commits)
- **AND** all three rows (user, credential, audit event) are present

### Requirement: Password-reset confirmation is atomic

The `ConfirmPasswordReset` use case SHALL commit the credential upsert, the reset-token consumption (`used_at`), the refresh-token revocation, and the audit event in a single database transaction. A failure in any write MUST roll back the credential update, leaving the user's password unchanged.

#### Scenario: Token-consumption failure preserves the old password

- **GIVEN** a valid unconsumed password-reset token for user `u`
- **AND** the internal-token writer is configured to raise on `mark_internal_token_used`
- **WHEN** `ConfirmPasswordReset` executes
- **THEN** `u`'s credential still matches the original password
- **AND** the reset token is still marked unconsumed
- **AND** existing refresh tokens for `u` are still valid

### Requirement: Email-verification confirmation is atomic and lock-protected

The `ConfirmEmailVerification` use case SHALL read the verification token with a row lock (`FOR UPDATE`) inside a transaction that also performs `mark_user_verified`, `mark_internal_token_used`, and the audit event. Two concurrent submissions of the same token MUST result in exactly one success and exactly one audit event.

#### Scenario: Concurrent submissions are serialized

- **GIVEN** a valid unconsumed email-verification token for user `u`
- **WHEN** two threads submit the same token concurrently against a real Postgres database
- **THEN** exactly one thread receives `Ok(...)`; the other receives an `Err` indicating the token was already used
- **AND** exactly one `auth.email_verified` audit event is recorded
- **AND** `u.is_verified` is `true`

### Requirement: AuthRepositoryPort exposes a registration transaction

The `AuthRepositoryPort` SHALL expose a `register_user_transaction()` context manager. Inside the context, callers receive a writer with `create_user(...)`, `upsert_credential(...)`, and `record_audit_event(...)` methods. The writer MUST NOT auto-commit per call. On normal exit the surrounding session commits; on exception it rolls back.

#### Scenario: Writer methods do not auto-commit

- **GIVEN** an open `register_user_transaction()` context
- **WHEN** the caller invokes `create_user(...)` and then exits the context via exception
- **THEN** the user row is not visible from a separate connection
- **AND** no `UserTable` row exists for that email

### Requirement: AuthInternalTokenTransactionPort covers credential upsert and user verification

The internal-token transaction writer SHALL expose `upsert_credential(...)` and `mark_user_verified(...)` alongside the existing token-consumption methods, so that `ConfirmPasswordReset` and `ConfirmEmailVerification` can run their complete state changes inside one transaction.

#### Scenario: Password-reset confirmation is atomic across token consumption and credential upsert

- **GIVEN** an open internal-token transaction for a password-reset confirmation
- **WHEN** `upsert_credential(...)` raises after the token row has been marked consumed
- **THEN** the surrounding session rolls back
- **AND** the reset token row is still in its pre-consumption state when read from a separate connection
- **AND** the credential row is unchanged

#### Scenario: Email-verification confirmation is atomic across token consumption and user-verified flag

- **GIVEN** an open internal-token transaction for an email-verification confirmation
- **WHEN** `mark_user_verified(...)` and the token-consumption update both succeed and the context exits normally
- **THEN** a separate connection observes `is_verified = true` AND the token marked consumed in the same snapshot
- **AND** neither change is observable from a separate connection before the context exits
