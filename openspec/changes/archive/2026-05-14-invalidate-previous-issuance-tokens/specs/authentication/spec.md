## ADDED Requirements

### Requirement: Token re-issuance invalidates prior unused tokens

`RequestPasswordReset` and `RequestEmailVerification` SHALL, inside the same transaction that inserts the new token, stamp `used_at = now()` on every prior unused token row for the same `(user_id, purpose)`. Only the most-recently-issued token MUST remain live.

#### Scenario: Re-issued reset invalidates the prior one

- **GIVEN** a user with one unused password-reset token issued at time T0
- **WHEN** the user requests another password reset at time T1
- **THEN** the T0 token's `used_at` is set
- **AND** the T1 token's `used_at` is NULL
- **AND** a confirm attempt with the T0 token returns `Err(TokenAlreadyUsed)`

#### Scenario: Re-issued verification invalidates the prior one

- **GIVEN** a user with one unused email-verification token issued at time T0
- **WHEN** the user requests another verification email at time T1
- **THEN** the T0 token's `used_at` is set
- **AND** the T1 token's `used_at` is NULL
- **AND** a confirm attempt with the T0 token returns `Err(TokenAlreadyUsed)`

#### Scenario: Invalidation runs in the same transaction as the insert

- **GIVEN** a `RequestPasswordReset` invocation wired to a transaction that will fail to commit
- **WHEN** the use case runs to the point of insert and the transaction rolls back
- **THEN** prior tokens for `(user_id, "password_reset")` are still unstamped (`used_at IS NULL`)
- **AND** no new token row is present
