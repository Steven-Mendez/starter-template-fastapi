## ADDED Requirements

### Requirement: Self-views do not expose internal counters

Self-view responses (`GET /me`, `PATCH /me`) SHALL NOT include internal fields used for caching, invalidation, or auditing. On the current `User` entity the exhaustive redacted set is `{"authz_version"}`. The `User` entity no longer carries a password hash (credentials live in the `authentication` feature's `credentials` table), so no credential field is in scope. Admin views (`GET /admin/users`, etc.) MAY continue to include `authz_version` and other internal fields.

A unit test SHALL pin the symmetric difference of `UserPublic.model_fields` and `UserPublicSelf.model_fields` to exactly `{"authz_version"}`, so any future field addition to either schema forces a deliberate decision.

#### Scenario: GET /me omits authz_version

- **GIVEN** user U is authenticated and has a non-zero `authz_version`
- **WHEN** U calls `GET /me`
- **THEN** the response status is `200`
- **AND** the response body does NOT contain the key `authz_version`
- **AND** the response body DOES contain `id`, `email`, and `created_at`

#### Scenario: PATCH /me omits authz_version

- **GIVEN** user U is authenticated
- **WHEN** U calls `PATCH /me` with a valid profile update
- **THEN** the response status is `200`
- **AND** the response body does NOT contain the key `authz_version`

#### Scenario: GET /admin/users includes authz_version

- **GIVEN** an admin caller with permission `read` on `system:main`
- **WHEN** the admin calls `GET /admin/users`
- **THEN** the response status is `200`
- **AND** every user object in the response includes the key `authz_version`

#### Scenario: Schema field-set drift is detected

- **GIVEN** the Pydantic schemas `UserPublic` and `UserPublicSelf`
- **WHEN** the field-difference unit test runs
- **THEN** `set(UserPublic.model_fields) - set(UserPublicSelf.model_fields)` equals exactly `{"authz_version"}`
- **AND** `set(UserPublicSelf.model_fields) - set(UserPublic.model_fields)` equals the empty set

#### Scenario: Drift after a new field is added trips the pin test

- **GIVEN** a hypothetical commit that adds a new field `last_seen_at` to `UserPublic` but not to `UserPublicSelf`
- **WHEN** the field-difference unit test runs
- **THEN** the assertion fails because the symmetric difference is now `{"authz_version", "last_seen_at"}`, not `{"authz_version"}`
- **AND** the failure message names the leaked field so the contributor must decide whether to also add it to `UserPublicSelf` or update the documented redaction set
