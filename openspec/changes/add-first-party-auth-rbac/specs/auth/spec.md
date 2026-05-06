## ADDED Requirements

### Requirement: User registration
The system MUST provide `POST /auth/register` to create a first-party user with a normalized lowercase email, Argon2id password hash, active status, unverified email status, and non-admin default role assignment when the configured default role exists.

#### Scenario: Successful registration
- **WHEN** a client submits a new valid email and password
- **THEN** the system MUST create the user, store only a password hash, assign no administrative permissions, and return a safe public user response

#### Scenario: Duplicate email
- **WHEN** a client submits an email that already exists after normalization
- **THEN** the system MUST reject the request without creating another user

### Requirement: Password hashing
The system MUST hash passwords with Argon2id using a maintained password hashing library and MUST never store or log plaintext passwords.

#### Scenario: Password stored after registration
- **WHEN** registration succeeds
- **THEN** the persisted password value MUST be a verifiable Argon2 hash and MUST NOT equal the submitted password

#### Scenario: Password verification failure
- **WHEN** a submitted password does not verify against the stored hash
- **THEN** the system MUST reject authentication with a generic invalid-credentials error

### Requirement: User login
The system MUST provide `POST /auth/login` to authenticate by normalized email and password, update `last_login_at`, issue a short-lived JWT access token, and issue a rotating opaque refresh token.

#### Scenario: Successful login
- **WHEN** an active user submits valid credentials
- **THEN** the system MUST return an access token in JSON and set the refresh token cookie

#### Scenario: Invalid credentials
- **WHEN** the email does not exist or the password is wrong
- **THEN** the system MUST return a generic invalid-credentials error without revealing which field failed

### Requirement: Access token
The system MUST issue JWT access tokens with `sub`, `exp`, `iat`, `nbf`, `jti`, `roles`, and `authz_version`, and MUST validate signature, expiration, algorithm, issuer, and audience when those settings are configured.

#### Scenario: Valid access token
- **WHEN** a protected endpoint receives a valid bearer access token for an active user
- **THEN** the system MUST authenticate the request principal

#### Scenario: Invalid access token
- **WHEN** a protected endpoint receives a missing, malformed, expired, stale, or invalid bearer access token
- **THEN** the system MUST return `401` with a bearer authentication challenge

### Requirement: Refresh token storage
The system MUST issue random opaque refresh tokens and MUST store only unique hashes of refresh tokens in PostgreSQL.

#### Scenario: Refresh token created
- **WHEN** login or refresh succeeds
- **THEN** the system MUST persist a refresh token record with token hash, user id, family id, expiration, creation metadata, and no raw token value

### Requirement: Refresh token rotation
The system MUST provide `POST /auth/refresh` and MUST rotate the refresh token on every successful use.

#### Scenario: Successful refresh
- **WHEN** a valid unexpired refresh token is submitted through the configured cookie
- **THEN** the system MUST revoke the old token, create a replacement token in the same family, return a new access token, and set a new refresh cookie

#### Scenario: Reuse of revoked refresh token
- **WHEN** a revoked refresh token is submitted again
- **THEN** the system MUST revoke the entire refresh token family and return `401`

### Requirement: Logout
The system MUST provide `POST /auth/logout` to revoke the current refresh token when present and clear the refresh cookie.

#### Scenario: Current session logout
- **WHEN** a client calls logout with a valid refresh cookie
- **THEN** the system MUST revoke that refresh token and delete the cookie

#### Scenario: Missing refresh cookie logout
- **WHEN** a client calls logout without a refresh cookie
- **THEN** the system MUST return a safe success response without leaking session state

### Requirement: Global session revocation
The system MUST provide `POST /auth/logout-all` to revoke all refresh tokens for the current authenticated user.

#### Scenario: Logout all sessions
- **WHEN** an active authenticated user calls logout-all
- **THEN** the system MUST revoke all non-revoked refresh tokens for that user and clear the current refresh cookie

### Requirement: Current user
The system MUST provide `GET /auth/me` to return the authenticated active user's public profile, roles, and permissions visible to that user.

#### Scenario: Authenticated current user
- **WHEN** an active authenticated user calls `/auth/me`
- **THEN** the system MUST return the user's id, email, active state, verified state, roles, and permissions without secret fields

### Requirement: Active user enforcement
The system MUST distinguish a valid token for an inactive user from an invalid token and MUST block inactive users from protected operations.

#### Scenario: Inactive user with valid token
- **WHEN** an inactive user presents an otherwise valid access token
- **THEN** the system MUST return `403`

### Requirement: Password reset
The system MUST provide `POST /auth/password/forgot` and `POST /auth/password/reset` using opaque internal tokens stored only as hashes with expiration and one-time use.

#### Scenario: Password reset requested
- **WHEN** a password reset is requested for any email
- **THEN** the system MUST return a generic response and, if the user exists, create a hashed expiring password reset token

#### Scenario: Password reset completed
- **WHEN** a valid unused password reset token and a new password are submitted
- **THEN** the system MUST update the password hash, mark the token used, revoke existing sessions, and increment authorization version

#### Scenario: Invalid password reset token
- **WHEN** a missing, expired, used, or invalid reset token is submitted
- **THEN** the system MUST reject the reset without changing the password

### Requirement: Email verification
The system MUST provide `POST /auth/email/verify/request` and `POST /auth/email/verify` using opaque internal tokens stored only as hashes with expiration and one-time use.

#### Scenario: Email verification requested
- **WHEN** email verification is requested by an authenticated user
- **THEN** the system MUST create a hashed expiring email verification token for that user

#### Scenario: Email verified
- **WHEN** a valid unused email verification token is submitted
- **THEN** the system MUST mark the user's email as verified and mark the token used

### Requirement: Authentication audit events
The system MUST persist audit events for security-relevant authentication actions without storing passwords, raw tokens, full hashes, or secrets.

#### Scenario: Login failure audited
- **WHEN** a login attempt fails
- **THEN** the system MUST record a safe audit event with event type and request metadata where available

#### Scenario: Refresh token reuse audited
- **WHEN** refresh token reuse is detected
- **THEN** the system MUST record a safe audit event and revoke the token family

### Requirement: Local rate limiting
The system MUST provide a configurable local rate limit for sensitive authentication endpoints without Redis or external services.

#### Scenario: Rate limit exceeded
- **WHEN** a client exceeds the configured local limit for a sensitive auth endpoint
- **THEN** the system MUST reject the request with a rate-limit response

### Requirement: Secure configuration
The system MUST read auth configuration from environment-backed settings and MUST document required variables in `.env.example` without committing real secrets.

#### Scenario: Missing JWT secret in protected environment
- **WHEN** the app runs outside a test/development-safe configuration without a JWT secret
- **THEN** the system MUST fail safely or reject token issuance rather than generating a real secret in code

### Requirement: Cookie security and CSRF guard
The system MUST set refresh token cookies as HttpOnly and MUST apply configured Secure and SameSite attributes. Cookie-backed refresh/logout endpoints MUST include CSRF mitigation appropriate to the current configuration.

#### Scenario: Refresh cookie set
- **WHEN** login or refresh succeeds
- **THEN** the response MUST set the refresh cookie with HttpOnly, configured Secure, configured SameSite, and `/auth` path attributes

#### Scenario: Cross-origin cookie refresh rejected
- **WHEN** a cookie-backed refresh request includes an untrusted Origin under a restrictive origin configuration
- **THEN** the system MUST reject the request

### Requirement: Updated documentation checks
The change MUST use current Context7 documentation checks for the detected libraries before implementation decisions are finalized.

#### Scenario: Documentation checks recorded
- **WHEN** the OpenSpec design is completed
- **THEN** it MUST list consulted libraries, detected versions where available, confirmed APIs, decisions adjusted by documentation, and limitations

### Requirement: Authentication tests
The system MUST include tests for successful and failed authentication flows, password hashing, refresh rotation and reuse detection, logout, logout-all, inactive users, password reset, email verification, secure errors, and token validation.

#### Scenario: Auth test suite
- **WHEN** the relevant test suite runs
- **THEN** tests MUST verify the required authentication behavior and security failure paths
